from unittest.mock import MagicMock

import pytest

from prompts import (
    CHUNK_PROMPTS,
    PROMPTS,
    SUMMARY_MODES,
    SUMMARY_PROMPT_BRIEF_RU,
    SUMMARY_PROMPT_DETAILED_RU,
    SUMMARY_PROMPT_MEDIUM_RU,
    get_prompt,
)
from providers.llm import LLMSummarizer


def test_prompts_has_ru_language() -> None:
    assert "ru" in PROMPTS


def test_prompts_ru_has_all_modes() -> None:
    assert set(PROMPTS["ru"]) == {"brief", "medium", "detailed"}


def test_summary_modes_constant() -> None:
    assert SUMMARY_MODES == {"brief", "medium", "detailed"}


def test_all_prompts_contain_placeholder() -> None:
    for lang, modes in PROMPTS.items():
        for mode, (_, user_template) in modes.items():
            assert "{transcript}" in user_template, f"{lang}/{mode!r} missing {{transcript}} placeholder"


def test_default_prompt_is_medium() -> None:
    s = LLMSummarizer(model="test")
    assert s._prompt_template is PROMPTS["ru"]["medium"]


def test_prompts_map_to_correct_constants() -> None:
    assert PROMPTS["ru"]["brief"][1] is SUMMARY_PROMPT_BRIEF_RU
    assert PROMPTS["ru"]["medium"][1] is SUMMARY_PROMPT_MEDIUM_RU
    assert PROMPTS["ru"]["detailed"][1] is SUMMARY_PROMPT_DETAILED_RU


def test_transcript_only_in_user_template() -> None:
    for lang, modes in PROMPTS.items():
        for mode, (system, user_template) in modes.items():
            assert "{transcript}" not in system, f"{lang}/{mode!r}: placeholder leaked into system prompt"
            assert "{transcript}" in user_template, f"{lang}/{mode!r}: placeholder missing from user template"


def test_user_templates_have_transcript_delimiters() -> None:
    for lang, modes in PROMPTS.items():
        for mode, (_, user_template) in modes.items():
            assert "<transcript>" in user_template, f"{lang}/{mode!r}: missing <transcript> tag"
            assert "</transcript>" in user_template, f"{lang}/{mode!r}: missing </transcript> tag"


def test_system_prompt_has_injection_warning() -> None:
    for lang, modes in PROMPTS.items():
        for mode, (system, _) in modes.items():
            assert "transcript" in system.lower(), f"{lang}/{mode!r}: system prompt doesn't mention transcript boundary"


def test_all_prompts_per_language_share_system_prompt() -> None:
    for lang, modes in PROMPTS.items():
        system_prompts = {system for system, _ in modes.values()}
        assert len(system_prompts) == 1, f"All modes for language {lang!r} should use the same system prompt"


def test_chunk_prompts_has_ru() -> None:
    assert "ru" in CHUNK_PROMPTS
    system, user_template = CHUNK_PROMPTS["ru"]
    assert "{transcript}" in user_template
    assert "<transcript>" in user_template


def test_get_prompt_returns_correct_template() -> None:
    result = get_prompt("ru", "brief")
    assert result is PROMPTS["ru"]["brief"]


def test_get_prompt_unknown_language_raises() -> None:
    with pytest.raises(KeyError, match="Unsupported summary language"):
        get_prompt("en", "brief")


def test_get_prompt_unknown_mode_raises() -> None:
    with pytest.raises(KeyError, match="not available"):
        get_prompt("ru", "ultra")


def test_build_messages_structure() -> None:
    summarizer = LLMSummarizer(model="test")
    messages = summarizer._build_messages("hello world")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_messages_transcript_in_user_only() -> None:
    summarizer = LLMSummarizer(model="test")
    messages = summarizer._build_messages("secret meeting content")
    assert "secret meeting content" in messages[1]["content"]
    assert "secret meeting content" not in messages[0]["content"]


def test_build_messages_transcript_wrapped_in_delimiters() -> None:
    summarizer = LLMSummarizer(model="test")
    messages = summarizer._build_messages("my transcript")
    user_content = messages[1]["content"]
    assert "<transcript>" in user_content
    assert "my transcript" in user_content
    assert "</transcript>" in user_content


def test_build_messages_str_template_uses_system_prompt() -> None:
    summarizer = LLMSummarizer(model="test", prompt_template="Task: {transcript}")
    messages = summarizer._build_messages("hello")
    assert messages[0]["role"] == "system"
    assert len(messages[0]["content"]) > 0
    assert "hello" in messages[1]["content"]


def _make_fake_openai(response_chunks: list[str], *, captured_kwargs: dict | None = None):
    """Return a fake openai.OpenAI class that streams the given response chunks."""

    class FakeChunk:
        def __init__(self, text: str) -> None:
            self.choices = [type("C", (), {"delta": type("D", (), {"content": text})()})()]

    class FakeStream:
        def __init__(self, chunks: list[str]) -> None:
            self._chunks = chunks

        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            for text in self._chunks:
                yield FakeChunk(text)

    class FakeCompletions:
        def create(self, model: str, messages: list, stream: bool, **kwargs) -> FakeStream:
            if captured_kwargs is not None:
                captured_kwargs.update(kwargs)
            return FakeStream(response_chunks)

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    def fake_openai_cls(**kw) -> FakeClient:
        if captured_kwargs is not None:
            captured_kwargs.update(kw)
        return FakeClient()

    return fake_openai_cls


def test_summarize_passes_messages_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    class FakeChunk:
        choices = [type("C", (), {"delta": type("D", (), {"content": "ok"})()})()]

    class FakeStream:
        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield FakeChunk()

    class FakeCompletions:
        def create(self, model: str, messages: list, stream: bool, **kwargs) -> FakeStream:
            captured.extend(messages)
            return FakeStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1")
    summarizer.summarize("test content")

    assert len(captured) == 2
    assert captured[0]["role"] == "system"
    assert captured[1]["role"] == "user"
    assert "test content" in captured[1]["content"]
    assert "test content" not in captured[0]["content"]


def test_timeout_passed_to_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    monkeypatch.setattr("openai.OpenAI", _make_fake_openai(["ok"], captured_kwargs=captured))
    monkeypatch.setattr("time.sleep", lambda _: None)

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1", timeout=42.0)
    summarizer.summarize("hi")

    assert captured.get("timeout") == 42.0


def test_retry_succeeds_on_second_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    call_count = [0]

    class FakeChunk:
        choices = [type("C", (), {"delta": type("D", (), {"content": "result"})()})()]

    class FakeStream:
        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield FakeChunk()

    class FakeCompletions:
        def create(self, **kw) -> FakeStream:
            call_count[0] += 1
            if call_count[0] == 1:
                raise openai.APITimeoutError(request=MagicMock())
            return FakeStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr("time.sleep", lambda _: None)

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1", max_retries=1, retry_backoff=0)
    result = summarizer.summarize("content")

    assert result == "result"
    assert call_count[0] == 2


def test_retry_on_httpx_error_mid_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network error raised while iterating the SSE stream is retryable, not fatal."""
    import httpx

    call_count = [0]

    class FailingStream:
        def __enter__(self) -> "FailingStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield type("C", (), {"choices": [type("C", (), {"delta": type("D", (), {"content": "partial"})()})()]})()
            raise httpx.ReadError("connection reset mid-stream")

    class OkChunk:
        choices = [type("C", (), {"delta": type("D", (), {"content": "result"})()})()]

    class OkStream:
        def __enter__(self) -> "OkStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield OkChunk()

    class FakeCompletions:
        def create(self, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return FailingStream()
            return OkStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr("time.sleep", lambda _: None)

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1", max_retries=1, retry_backoff=0)
    result = summarizer.summarize("content")

    assert result == "result"
    assert call_count[0] == 2


def test_retry_exhausted_raises_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    class FakeCompletions:
        def create(self, **kw) -> None:
            raise openai.APIConnectionError(request=MagicMock())

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr("time.sleep", lambda _: None)

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1", max_retries=2, retry_backoff=0)
    with pytest.raises(openai.APIConnectionError):
        summarizer.summarize("content")


def test_non_retryable_error_propagates_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = [0]

    class FakeCompletions:
        def create(self, **kw) -> None:
            call_count[0] += 1
            raise ValueError("bad input")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr("time.sleep", lambda _: None)

    summarizer = LLMSummarizer(model="test", base_url="http://localhost:1234/v1", max_retries=2, retry_backoff=0)
    with pytest.raises(ValueError, match="bad input"):
        summarizer.summarize("content")

    assert call_count[0] == 1


# ── Chunking ──────────────────────────────────────────────────────────────────


def test_split_into_chunks_basic() -> None:
    s = LLMSummarizer(model="test", max_chars=10)
    chunks = s._split_into_chunks("hello\nworld\nfoo")
    assert len(chunks) == 2
    assert "hello" in chunks[0]
    assert "world" in chunks[1] or "foo" in chunks[1]


def test_split_into_chunks_fits_in_one() -> None:
    s = LLMSummarizer(model="test", max_chars=100)
    chunks = s._split_into_chunks("short line\nanother")
    assert len(chunks) == 1


def test_split_into_chunks_single_long_line() -> None:
    s = LLMSummarizer(model="test", max_chars=10)
    long_line = "a" * 25
    chunks = s._split_into_chunks(long_line)
    assert len(chunks) == 3
    assert "".join(chunks) == long_line  # all text preserved, no loss


def test_chunked_summarize_all_chunks_processed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text from each chunk must appear in the merge call — including the last chunk."""
    call_messages: list[list[dict]] = []

    # LLM returns "ok" (2 chars) so merged summaries stay well within max_chars.
    class FakeChunk:
        choices = [type("C", (), {"delta": type("D", (), {"content": "ok"})()})()]

    class FakeStream:
        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield FakeChunk()

    class FakeCompletions:
        def create(self, model: str, messages: list, stream: bool, **kw) -> FakeStream:
            call_messages.append(messages)
            return FakeStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())

    # max_chars=50: lines of 30 chars each force 2 chunks;
    # merged summaries ("[Часть 1]\nok\n\n[Часть 2]\nok" ≈ 26 chars) fit in one call.
    max_chars = 50
    line1 = "a" * 30
    line2 = "b" * 30
    long_text = f"{line1}\n{line2}"  # 61 chars > max_chars → 2 chunks

    summarizer = LLMSummarizer(
        model="test",
        base_url="http://localhost:1234/v1",
        max_chars=max_chars,
        chunking_mode="chunk",
    )
    summarizer.summarize(long_text)

    # 3 LLM calls: chunk 1, chunk 2, merge
    assert len(call_messages) == 3

    user1 = call_messages[0][1]["content"]
    user2 = call_messages[1][1]["content"]
    merge_user = call_messages[2][1]["content"]

    assert line1 in user1
    assert line2 in user2
    assert "[Часть 1]" in merge_user
    assert "[Часть 2]" in merge_user


def test_truncate_mode_does_not_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = [0]

    class FakeChunk:
        choices = [type("C", (), {"delta": type("D", (), {"content": "ok"})()})()]

    class FakeStream:
        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __iter__(self):
            yield FakeChunk()

    class FakeCompletions:
        def create(self, **kw) -> FakeStream:
            call_count[0] += 1
            return FakeStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient())

    long_text = "word " * 100  # longer than max_chars=20
    summarizer = LLMSummarizer(
        model="test",
        base_url="http://localhost:1234/v1",
        max_chars=20,
        chunking_mode="truncate",
    )
    summarizer.summarize(long_text)

    assert call_count[0] == 1  # only one call — no chunking
