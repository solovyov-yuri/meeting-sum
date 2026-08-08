from __future__ import annotations

import pytest

from config import (
    Settings,
    SummarizationModelSettings,
    SummarizationSettings,
    TranscriptionModelSettings,
    TranscriptionSettings,
)
from providers.factory import make_summarizer, make_transcriber


def _settings(
    *,
    sum_model: SummarizationModelSettings | None = None,
    summary_language: str | None = None,
    transcription_language: str = "ru",
    tr_model: TranscriptionModelSettings | None = None,
) -> Settings:
    return Settings(
        transcription=TranscriptionSettings(
            language=transcription_language,
            model=tr_model or TranscriptionModelSettings(),
        ),
        summarization=SummarizationSettings(
            language=summary_language,
            model=sum_model or SummarizationModelSettings(),
        ),
    )


def test_make_summarizer_unknown_provider() -> None:
    with pytest.raises(ValueError, match="provider"):
        make_summarizer(Settings(), "grok", "medium")


def test_make_summarizer_unknown_mode() -> None:
    with pytest.raises(ValueError, match="not available|Unsupported"):
        make_summarizer(Settings(), "ollama", "ultra")


def test_make_summarizer_base_url_from_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    make_summarizer(Settings(), "ollama", "medium")

    assert captured["base_url"] == "http://localhost:11434/v1"


def test_make_summarizer_xai_base_url_from_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(api_key="sk-test"))
    make_summarizer(settings, "xai", "medium")

    assert captured["base_url"] == "https://api.x.ai/v1"


def test_make_summarizer_settings_base_url_takes_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(base_url="http://custom:9999/v1", api_key="sk-test"))
    make_summarizer(settings, "ollama", "medium")

    assert captured["base_url"] == "http://custom:9999/v1"


def test_make_summarizer_api_key_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(api_key="sk-test"))
    make_summarizer(settings, "ollama", "medium")

    assert captured["api_key"] == "sk-test"


def test_make_summarizer_external_provider_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # SEC-004: even with OPENAI_API_KEY in the environment, an external provider with
    # no configured key must fail loudly rather than let the OpenAI SDK read that env var.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-be-ignored")
    settings = _settings(sum_model=SummarizationModelSettings(provider="openai", api_key=None))
    with pytest.raises(ValueError, match="No API key configured for external provider"):
        make_summarizer(settings, "openai", "medium")


def test_make_summarizer_local_provider_without_key_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(provider="ollama", api_key=None))
    make_summarizer(settings, "ollama", "medium")

    assert captured["api_key"] is None


def test_make_summarizer_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    make_summarizer(Settings(), "ollama", "medium", model_override="llama3:latest")

    assert captured["model"] == "llama3:latest"


def test_make_summarizer_default_model_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(name="my-default-model"))
    make_summarizer(settings, "ollama", "medium")

    assert captured["model"] == "my-default-model"


def test_make_summarizer_passes_num_ctx(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    settings = _settings(sum_model=SummarizationModelSettings(num_ctx=32768))
    make_summarizer(settings, "ollama", "medium")

    assert captured["num_ctx"] == 32768


def test_make_summarizer_num_ctx_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    make_summarizer(Settings(), "ollama", "medium")

    assert captured["num_ctx"] is None


def test_make_transcriber_passes_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.whisper as whisper_mod

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", fake_init)
    settings = _settings(tr_model=TranscriptionModelSettings(name="medium", device="cpu"))
    make_transcriber(settings)

    assert captured["model_name"] == "medium"
    assert captured["device"] == "cpu"


def test_make_transcriber_faster_whisper_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.whisper as whisper_mod

    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    # provider defaults to faster-whisper — must not raise.
    make_transcriber(Settings())


def test_make_transcriber_unknown_provider_rejected() -> None:
    settings = _settings(tr_model=TranscriptionModelSettings(provider="whisper-cpp"))
    with pytest.raises(ValueError, match="transcription provider"):
        make_transcriber(settings)


def test_make_summarizer_uses_summary_language(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod
    from prompts import PROMPTS

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    make_summarizer(Settings(), "ollama", "brief", summary_language="ru")

    assert captured["prompt_template"] is PROMPTS["ru"]["brief"]


def test_make_summarizer_defaults_to_ru_when_no_summary_language(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod
    from prompts import PROMPTS

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    # Even with transcription.language="en", summary defaults to "ru".
    settings = _settings(transcription_language="en", summary_language=None)
    make_summarizer(settings, "ollama", "medium")

    assert captured["prompt_template"] is PROMPTS["ru"]["medium"]


def test_make_summarizer_unknown_summary_language() -> None:
    with pytest.raises(ValueError, match="Unsupported summary language"):
        make_summarizer(Settings(), "ollama", "medium", summary_language="en")


def test_make_summarizer_chunk_prompt_matches_language(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.llm as llm_mod
    from prompts import CHUNK_PROMPTS

    captured: dict = {}

    def fake_init(self: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(llm_mod.LLMSummarizer, "__init__", fake_init)
    make_summarizer(Settings(), "ollama", "medium", summary_language="ru")

    assert captured["chunk_prompt"] is CHUNK_PROMPTS["ru"]
