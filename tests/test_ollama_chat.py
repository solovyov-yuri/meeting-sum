import json
from unittest.mock import MagicMock

import httpx
import pytest

from prompts import JSON_PROMPTS
from providers.llm import LLMSummarizer
from providers.ollama_chat import GenerationIncomplete, SummarizationCancelled, chat, estimate_tokens


def test_native_transport_controls_context_and_schema():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, text='{"message":{"content":"готово"}}\n{"done":true,"done_reason":"stop"}\n')

    schema = {"type": "object"}
    with httpx.Client(base_url="http://localhost/prefix/", transport=httpx.MockTransport(handle)) as client:
        result = chat(
            client,
            model="qwen",
            messages=[],
            num_ctx=4096,
            num_predict=1024,
            response_format={"type": "json_schema", "json_schema": {"schema": schema}},
            console=MagicMock(),
            cancelled=lambda: False,
        )
    assert result == "готово"
    assert requests[0].url.path == "/prefix/api/chat"
    body = json.loads(requests[0].content)
    assert body["options"] == {"num_ctx": 4096, "num_predict": 1024, "temperature": 0}
    assert body["think"] is False
    assert body["truncate"] is False
    assert body["shift"] is False
    assert body["format"] == schema


@pytest.mark.parametrize(
    "events",
    [
        [{"message": {"content": "partial"}}],
        [{"done": True}],
        [{"message": {"content": "partial"}, "done": True, "done_reason": "length"}],
        [{"error": "failure"}],
    ],
)
def test_native_rejects_incomplete_or_empty_response(events):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="\n".join(map(json.dumps, events))))
    with httpx.Client(base_url="http://localhost/", transport=transport) as client:
        with pytest.raises(GenerationIncomplete):
            chat(
                client,
                model="q",
                messages=[],
                num_ctx=4096,
                num_predict=1024,
                response_format=None,
                console=MagicMock(),
                cancelled=lambda: False,
            )


def test_native_stops_stream_on_cancel():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text='{"message":{"content":"x"}}'))
    with httpx.Client(base_url="http://localhost/", transport=transport) as client:
        with pytest.raises(SummarizationCancelled):
            chat(
                client,
                model="q",
                messages=[],
                num_ctx=4096,
                num_predict=1024,
                response_format=None,
                console=MagicMock(),
                cancelled=lambda: True,
            )


@pytest.mark.parametrize("context", [4096, 8192])
def test_budget_preserves_every_character_and_reserves_response(context):
    s = LLMSummarizer(model="q", ollama=True, num_ctx=context, json_prompt=JSON_PROMPTS["ru"]["medium"])
    text = "Начало встречи.\n" + "оченьдлиннаяреплика" * 1500 + "\nКонец встречи.\n"
    chunks = s._split_into_chunks(text)
    assert "".join(chunks) == text
    assert len(chunks) > 1
    for chunk in chunks:
        assert s._fits(chunk)
        for template in [s._prompt_template, s._chunk_prompt, s._json_prompt]:
            cost = sum(estimate_tokens(m["content"]) for m in s._build_messages(chunk, template))
            assert cost + s._output_tokens + 256 < context


def test_native_context_too_small_fails_before_request(monkeypatch):
    monkeypatch.setattr(httpx.Client, "stream", lambda *a, **k: pytest.fail("request sent"))
    with pytest.raises(ValueError, match="Контекст"):
        LLMSummarizer(model="q", ollama=True, num_ctx=1024).summarize("hello")


def test_final_fallback_reuses_completed_chunks(monkeypatch):
    s = LLMSummarizer(model="q", ollama=True, num_ctx=4096, json_prompt=JSON_PROMPTS["ru"]["medium"])
    calls = []

    def call(messages, client, console, response_format=None):
        calls.append(response_format)
        if response_format and response_format["json_schema"]["name"] == "evidence":
            return '{"keep": [0]}'
        if response_format:
            raise GenerationIncomplete("bad JSON")
        return "факт"

    monkeypatch.setattr(s, "_call_llm", call)
    text = "Реплика о плане работы.\n" * 250
    with pytest.raises(GenerationIncomplete):
        s.summarize(text, structured=True)
    before = len(calls)
    assert s.summarize(text) == "факт"
    assert len(calls) == before + 1
    s.summarize(text + "Новый вопрос.")
    assert len(calls) > before + 2  # a different transcript must not reuse old preparation


def test_nonshrinking_merge_fails_instead_of_truncating(monkeypatch):
    s = LLMSummarizer(model="q", ollama=True, num_ctx=4096)
    monkeypatch.setattr(s, "_summarize_one_chunk", lambda indexed, *a, **k: indexed[1])
    with pytest.raises(ValueError, match="Хвост не обрезан"):
        s.summarize("Все сведения должны сохраниться.\n" * 300)


def test_workflow_does_not_retry_cancelled_generation():
    from workflows import _generate_summary

    summarizer = MagicMock(supports_structured=True)
    summarizer.summarize.side_effect = SummarizationCancelled()
    with pytest.raises(SummarizationCancelled):
        _generate_summary(summarizer, "text", "medium")
    assert summarizer.summarize.call_count == 1


def test_factory_selects_native_transport_only_for_ollama():
    from config import Settings
    from providers.factory import make_summarizer

    assert make_summarizer(Settings(), "ollama", "medium")._ollama
    assert not make_summarizer(Settings(), "lm-studio", "medium")._ollama


def test_native_final_schema_rejection_falls_back_to_json(monkeypatch):
    s = LLMSummarizer(model="q", ollama=True, json_prompt=JSON_PROMPTS["ru"]["medium"])
    calls = []

    def call(*args, response_format=None):
        calls.append(response_format["type"])
        if len(calls) == 1:
            response = httpx.Response(400, request=httpx.Request("POST", "http://localhost/api/chat"))
            response.raise_for_status()
        return '{"intro":"готово"}'

    monkeypatch.setattr(s, "_call_llm", call)
    assert s.summarize("text", structured=True) == '{"intro":"готово"}'
    assert calls == ["json_schema", "json_object"]


def test_cancel_during_network_timeout_bypasses_retry(monkeypatch):
    s = LLMSummarizer(model="q", ollama=True, max_retries=2)
    cancelled = False
    s.set_callbacks(lambda: cancelled, lambda message: None)

    def fail(*args, **kwargs):
        nonlocal cancelled
        cancelled = True
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr("providers.ollama_chat.chat", fail)
    monkeypatch.setattr("time.sleep", lambda delay: pytest.fail("cancelled request retried"))
    with pytest.raises(SummarizationCancelled):
        s.summarize("text")


def test_evidence_is_verbatim_in_source_order(monkeypatch):
    s = LLMSummarizer(model="q", ollama=True)
    excerpts = [f"Факт {n}: " + "а" * 460 + "\n" for n in range(9)]
    monkeypatch.setattr(s, "_call_llm", lambda *a, **k: '{"keep": [8, 0, 4]}')
    result = s._summarize_one_chunk((1, "".join(excerpts)), None, None)
    assert result == "\n".join(excerpts[n].strip() for n in [0, 4, 8])


@pytest.mark.parametrize("indices", [[999], [True], [], [0, 0], [0, 1, 2, 3]])
def test_invalid_evidence_rejected(monkeypatch, indices):
    s = LLMSummarizer(model="q", ollama=True)
    monkeypatch.setattr(s, "_call_llm", lambda *a, **k: json.dumps({"keep": indices}))
    with pytest.raises(ValueError, match="номера"):
        s._summarize_one_chunk((1, ("а" * 480 + "\n") * 9), None, None)
