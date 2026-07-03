from __future__ import annotations

from pathlib import Path

import pytest

import workflows
from config import Settings
from transcript import Segment, Transcript
from workflows import ProgressEvent, RunOptions, is_external_provider, run_one_file


class FakeTranscriber:
    def __init__(self, transcript: Transcript) -> None:
        self._transcript = transcript

    def transcribe(
        self, audio: Path, language: str = "ru", *, on_progress: object = None
    ) -> Transcript:
        if callable(on_progress):
            on_progress(0.5)  # emit one progress tick so the wiring is exercised
        return self._transcript


class FakeSummarizer:
    supports_structured = False

    def __init__(self, response: str = "итоги встречи") -> None:
        self.response = response

    def summarize(self, text: str, structured: bool = False) -> str:
        return self.response


class FailingSummarizer:
    supports_structured = False

    def summarize(self, text: str, structured: bool = False) -> str:
        raise ConnectionError("LLM down")


@pytest.fixture()
def audio_file(tmp_path: Path) -> Path:
    a = tmp_path / "meeting.wav"
    a.write_bytes(b"RIFF" + b"\x00" * 32)
    return a


def _patch_providers(
    monkeypatch: pytest.MonkeyPatch,
    transcript: Transcript,
    summarizer: object,
) -> None:
    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber(transcript))
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: summarizer,
    )


# ── is_external_provider ──────────────────────────────────────────────────────


def test_is_external_openai_default() -> None:
    assert is_external_provider(None, "openai") is True


def test_is_external_localhost_not_external() -> None:
    assert is_external_provider("http://localhost:11434/v1", "ollama") is False


def test_is_external_remote_host() -> None:
    assert is_external_provider("https://api.x.ai/v1", "xai") is True


# ── run modes: transcribe-only / preprocess-only ───────────────────────────────


def test_run_one_file_transcribe_only_skips_summarize(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import providers.factory as factory_mod

    tr = Transcript(segments=(Segment(0.0, 1.0, "привет"),))
    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber(tr))
    # summarizer must NOT be built for transcribe-only — make it explode if constructed.
    def _no_summarizer(*_a: object, **_k: object) -> object:
        raise AssertionError("make_summarizer must not be called in transcribe-only mode")

    monkeypatch.setattr(factory_mod, "make_summarizer", _no_summarizer)

    events: list[ProgressEvent] = []
    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings(), progress=events.append, stop_after="transcribe")

    assert result.status == "success"
    assert (tmp_path / "tr.txt").exists()
    assert not (tmp_path / "sum.txt").exists()  # summarization skipped
    assert result.summary_path is None
    steps = {(e.step, e.status) for e in events}
    assert ("transcribe", "success") in steps
    assert ("summarize", "success") not in steps


def test_run_one_file_transcribe_only_empty_is_success(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber(Transcript(segments=())))
    monkeypatch.setattr(factory_mod, "make_summarizer", lambda *a, **k: FakeSummarizer())

    options = RunOptions(audio_path=audio_file, transcript_path=tmp_path / "tr.txt", provider="ollama")
    result = run_one_file(options, settings=Settings(), stop_after="transcribe")
    # Empty transcript is success-with-warning in transcribe-only mode (not failed).
    assert result.status == "success"
    assert (tmp_path / "tr.txt").exists()


def test_run_one_file_force_preprocess_overrides_disabled(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import contextlib

    seen_enabled: list[bool] = []

    @contextlib.contextmanager
    def fake_prepared(audio: Path, cfg: object):  # type: ignore[no-untyped-def]
        seen_enabled.append(cfg.enabled)  # type: ignore[attr-defined]
        yield audio

    monkeypatch.setattr("preprocessing.prepared_audio", fake_prepared)
    _patch_providers(monkeypatch, Transcript(segments=(Segment(0.0, 1.0, "x"),)), FakeSummarizer())

    events: list[ProgressEvent] = []
    options = RunOptions(audio_path=audio_file, transcript_path=tmp_path / "tr.txt", summary_path=tmp_path / "s.txt", provider="ollama")
    # Settings() defaults preprocessing.enabled=False; force_preprocess must flip it on.
    run_one_file(options, settings=Settings(), progress=events.append, force_preprocess=True)

    assert seen_enabled == [True]
    assert ("preprocess", "running") in {(e.step, e.status) for e in events}


def test_preprocess_one_writes_output(tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_preprocess(inp: Path, out: Path, cfg: object) -> None:
        out.write_bytes(b"wav")

    monkeypatch.setattr("preprocessing.preprocess_audio", fake_preprocess)
    result = workflows.preprocess_one(RunOptions(audio_path=audio_file), settings=Settings(output_dir=tmp_path / "out"))

    assert result.status == "success"
    assert result.output_path == tmp_path / "out" / "meeting.preprocessed.wav"
    assert result.output_path.exists()
    assert result.transcript_path is None and result.summary_path is None


def test_preprocess_one_defaults_next_to_audio(tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("preprocessing.preprocess_audio", lambda inp, out, cfg: out.write_bytes(b"x"))
    result = workflows.preprocess_one(RunOptions(audio_path=audio_file), settings=Settings())
    assert result.output_path == audio_file.parent / "meeting.preprocessed.wav"


def test_preprocess_one_missing_audio(tmp_path: Path) -> None:
    result = workflows.preprocess_one(RunOptions(audio_path=tmp_path / "nope.wav"), settings=Settings())
    assert result.status == "failed"
    assert "не найден" in (result.error_message or "").lower()


# ── run_one_file ──────────────────────────────────────────────────────────────


def test_run_one_file_success(tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tr = Transcript(segments=(Segment(0.0, 1.0, "обсудили дорожную карту"),))
    _patch_providers(monkeypatch, tr, FakeSummarizer("*Тема встречи*\nИтоги готовы.\n\n*Решения и задачи*\n- готово"))

    events: list[ProgressEvent] = []
    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings(), progress=events.append)

    assert result.status == "success"
    assert result.transcript_path == tmp_path / "tr.txt"
    assert result.summary_path == tmp_path / "sum.txt"
    assert result.summary_json_path == tmp_path / "sum.json"
    assert (tmp_path / "tr.txt").exists()
    assert (tmp_path / "sum.txt").exists()
    assert (tmp_path / "sum.json").exists()
    # The raw response was parsed to a structured object and rendered back to canonical Markdown.
    assert "## Тема встречи" in result.summary_text
    assert "- готово" in result.summary_text
    assert "обсудили" in result.transcript_text
    steps_done = {(e.step, e.status) for e in events}
    assert ("transcribe", "success") in steps_done
    assert ("summarize", "success") in steps_done
    assert ("export", "success") in steps_done


def test_run_one_file_structured_json_path(tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path of the JSON feature: valid structured output is used and the text fallback is NOT taken."""
    import json as _json

    class StructuredSummarizer:
        supports_structured = True

        def __init__(self) -> None:
            self.calls: list[bool] = []

        def summarize(self, text: str, structured: bool = False) -> str:
            self.calls.append(structured)
            if structured:
                return _json.dumps(
                    {
                        "intro": "Кратко о встрече",
                        "sections": [{"title": "Тема А", "points": ["п1"], "actions": ["сделать"]}],
                        "joke": None,
                    },
                    ensure_ascii=False,
                )
            return "ТЕКСТОВЫЙ ФОЛЛБЭК — не должен использоваться"

    summarizer = StructuredSummarizer()
    _patch_providers(monkeypatch, Transcript(segments=(Segment(0.0, 1.0, "речь"),)), summarizer)

    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
        mode="medium",
    )
    result = run_one_file(options, settings=Settings(), progress=lambda e: None)

    assert result.status == "success"
    # Only the structured call was made — the text fallback was not taken.
    assert summarizer.calls == [True]
    assert "ФОЛЛБЭК" not in (result.summary_text or "")
    # The rendered Markdown reflects the structured object.
    assert "## Тема встречи\nКратко о встрече" in result.summary_text
    assert "## Тема: Тема А" in result.summary_text
    assert "- сделать" in result.summary_text
    # The .json export is the structured block object.
    data = _json.loads((tmp_path / "sum.json").read_text(encoding="utf-8"))
    assert data["blocks"][0]["heading"] == "Тема встречи"
    assert data["blocks"][0]["paragraphs"] == ["Кратко о встрече"]
    assert data["blocks"][1]["heading"] == "Тема: Тема А"
    assert data["blocks"][1]["groups"][1]["items"] == ["сделать"]


def test_run_one_file_emits_transcribe_percent(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CODE-006: the transcriber's per-segment callback surfaces as a transcribe progress event
    # carrying a real percent (the browser mock already showed a moving bar; now the real path does).
    tr = Transcript(segments=(Segment(0.0, 1.0, "x"),))
    _patch_providers(monkeypatch, tr, FakeSummarizer())
    events: list[ProgressEvent] = []
    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    run_one_file(options, settings=Settings(), progress=events.append)
    pcts = [e.percent for e in events if e.step == "transcribe" and e.percent is not None]
    assert 0.5 in pcts  # FakeTranscriber emits on_progress(0.5)


def test_run_one_file_partial_success_on_llm_failure(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tr = Transcript(segments=(Segment(0.0, 1.0, "hello"),))
    _patch_providers(monkeypatch, tr, FailingSummarizer())

    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings())

    assert result.status == "partial_success"
    assert (tmp_path / "tr.txt").exists(), "transcript must persist before LLM call"
    assert not (tmp_path / "sum.txt").exists()
    assert result.summary_path is None
    assert result.transcript_text is not None
    assert result.error_message


def test_run_one_file_empty_transcript_skips_llm(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"summarize": False}

    class TrackingSummarizer:
        supports_structured = False

        def summarize(self, text: str, structured: bool = False) -> str:
            called["summarize"] = True
            return "nope"

    _patch_providers(monkeypatch, Transcript(segments=()), TrackingSummarizer())

    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings())

    assert result.status == "failed"
    assert (tmp_path / "tr.txt").exists()
    assert not called["summarize"]
    assert not (tmp_path / "sum.txt").exists()
    assert "распознан" in result.error_message.lower()


def test_run_one_file_missing_audio(tmp_path: Path) -> None:
    options = RunOptions(audio_path=tmp_path / "nope.wav")
    result = run_one_file(options, settings=Settings())
    assert result.status == "failed"
    assert "не найден" in result.error_message.lower()


def test_run_one_file_unsupported_extension(tmp_path: Path) -> None:
    bad = tmp_path / "doc.pdf"
    bad.write_bytes(b"%PDF")
    result = run_one_file(RunOptions(audio_path=bad), settings=Settings())
    assert result.status == "failed"
    assert "формат" in result.error_message.lower()


def test_run_one_file_accepts_mp4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # REL-004: .mp4 is the user's real recording format — it must pass the extension gate.
    mp4 = tmp_path / "meeting.mp4"
    mp4.write_bytes(b"\x00" * 32)
    tr = Transcript(segments=(Segment(0.0, 1.0, "обсудили план"),))
    _patch_providers(monkeypatch, tr, FakeSummarizer())
    options = RunOptions(
        audio_path=mp4,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings())
    assert result.status == "success"


def test_run_one_file_cancel_before_transcribe(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, Transcript(segments=(Segment(0.0, 1.0, "x"),)), FakeSummarizer())
    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings(), cancel=lambda: True)
    assert result.status == "cancelled"
    assert not (tmp_path / "tr.txt").exists()


def test_run_one_file_cancel_after_transcribe_keeps_transcript(
    tmp_path: Path, audio_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ARCH-002: cancelling at the boundary *after* transcription must preserve the transcript
    # path (it is already on disk), so the user does not lose the pointer to it.
    _patch_providers(monkeypatch, Transcript(segments=(Segment(0.0, 1.0, "x"),)), FakeSummarizer())
    calls = {"n": 0}

    def cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # False before transcribe, True after

    options = RunOptions(
        audio_path=audio_file,
        transcript_path=tmp_path / "tr.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = run_one_file(options, settings=Settings(), cancel=cancel)
    assert result.status == "cancelled"
    assert result.transcript_path == tmp_path / "tr.txt"
    assert (tmp_path / "tr.txt").exists()


def test_run_one_file_unknown_provider_fails(tmp_path: Path, audio_file: Path) -> None:
    options = RunOptions(audio_path=audio_file, provider="grok")
    result = run_one_file(options, settings=Settings())
    assert result.status == "failed"
    assert "grok" in result.error_message.lower()


def _exploding_transcriber(settings: object) -> object:
    raise AssertionError("transcriber must not be built during resummarize")


def test_resummarize_one_uses_existing_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript_path = tmp_path / "tr.txt"
    transcript_path.write_text("[0.00s -> 1.00s] обсудили план\n", encoding="utf-8")

    import providers.factory as factory_mod

    # Prove no transcription happens: make_transcriber would raise if called.
    monkeypatch.setattr(factory_mod, "make_transcriber", _exploding_transcriber)
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer("резюме"),
    )

    options = RunOptions(
        audio_path=tmp_path / "meeting.wav",  # not read by resummarize
        transcript_path=transcript_path,
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = workflows.resummarize_one(options, settings=Settings())

    assert result.status == "success"
    assert (tmp_path / "sum.txt").exists()
    assert (tmp_path / "sum.json").exists()
    assert "резюме" in result.summary_text


def test_resummarize_one_non_utf8_transcript_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # REL-001: a cp1251-encoded transcript must yield a friendly failure, not a raw
    # UnicodeDecodeError traceback (it subclasses ValueError, so plain `except OSError` misses it).
    transcript_path = tmp_path / "tr.txt"
    transcript_path.write_bytes("[0.00s -> 1.00s] обсудили план\n".encode("cp1251"))

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", _exploding_transcriber)
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    options = RunOptions(
        audio_path=tmp_path / "meeting.wav",
        transcript_path=transcript_path,
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = workflows.resummarize_one(options, settings=Settings())
    assert result.status == "failed"
    assert "прочитать транскрипт" in result.error_message.lower()


def test_resummarize_one_missing_transcript(tmp_path: Path) -> None:
    options = RunOptions(
        audio_path=tmp_path / "meeting.wav",
        transcript_path=tmp_path / "missing.txt",
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = workflows.resummarize_one(options, settings=Settings())
    assert result.status == "failed"
    assert "не найден" in result.error_message.lower()


def test_resummarize_one_partial_on_llm_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript_path = tmp_path / "tr.txt"
    transcript_path.write_text("[0.00s -> 1.00s] текст\n", encoding="utf-8")

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", _exploding_transcriber)
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FailingSummarizer(),
    )

    options = RunOptions(
        audio_path=tmp_path / "meeting.wav",
        transcript_path=transcript_path,
        summary_path=tmp_path / "sum.txt",
        provider="ollama",
    )
    result = workflows.resummarize_one(options, settings=Settings())
    assert result.status == "partial_success"
    assert not (tmp_path / "sum.txt").exists()
    assert result.transcript_text is not None


def test_humanize_error_timeout() -> None:
    class APITimeoutError(Exception):
        pass

    assert "время ожидания" in workflows.humanize_error(APITimeoutError("x")).lower()
