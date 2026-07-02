from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import app

runner = CliRunner()


def test_help_no_cuda_import() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "transcribe" in result.output


def test_transcribe_help() -> None:
    result = runner.invoke(app, ["transcribe", "--help"])
    assert result.exit_code == 0


def test_summarize_help() -> None:
    result = runner.invoke(app, ["summarize", "--help"])
    assert result.exit_code == 0


def test_run_help() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_transcribe_missing_audio(tmp_path: Path) -> None:
    result = runner.invoke(app, ["transcribe", str(tmp_path / "nope.wav")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_summarize_missing_transcript(tmp_path: Path) -> None:
    result = runner.invoke(app, ["summarize", str(tmp_path / "nope.txt")])
    assert result.exit_code == 1
    assert "не найден" in result.output


def test_summarize_unknown_provider(tmp_path: Path) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello\n", encoding="utf-8")
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "grok"])
    assert result.exit_code == 1
    assert "provider" in result.output.lower()


def test_summarize_unknown_mode(tmp_path: Path) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello\n", encoding="utf-8")
    result = runner.invoke(app, ["summarize", str(transcript), "-m", "ultra"])
    assert result.exit_code == 1
    assert "mode" in result.output.lower()


def test_summarize_non_utf8_transcript(tmp_path: Path) -> None:
    # REL-001: a cp1251-encoded transcript must fail cleanly (exit 1), not dump a
    # UnicodeDecodeError traceback past the error boundary.
    transcript = tmp_path / "t.txt"
    transcript.write_bytes("[00:00] привет\n".encode("cp1251"))
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "ollama"])
    assert result.exit_code == 1
    assert "прочитать транскрипт" in result.output.lower()


def test_help_does_not_load_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    provider: bad-provider\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["summarize", "--help"])
    assert result.exit_code == 0


def test_config_error_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    provider: bad-provider\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["summarize", str(tmp_path / "t.txt")])
    assert result.exit_code == 1
    assert "Configuration error" in result.output


def test_run_saves_transcript_before_llm_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"\x00" * 16)
    transcript_file = tmp_path / "out.txt"
    summary_file = tmp_path / "out_summary.txt"

    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    # Repo config.yaml uses the external openai provider; give it a dummy key so the
    # factory's external-provider key check passes and the LLM path is exercised.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod

    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)

    def bad_summarize(self: object, text: str) -> str:
        raise ConnectionError("LLM down")

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", bad_summarize)

    result = runner.invoke(
        app,
        [
            "run",
            str(audio),
            "--transcript",
            str(transcript_file),
            "--summary",
            str(summary_file),
        ],
    )

    assert result.exit_code == 1
    assert "подключиться" in result.output.lower()
    assert transcript_file.exists(), "transcript must be saved before LLM is called"


def test_privacy_warning_for_openai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    # openai is external — supply a dummy key so the factory's key check passes.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "openai", "-o", str(tmp_path / "out.txt")])
    assert "Warning" in result.output
    assert "external" in result.output


def test_no_privacy_warning_for_localhost(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "ollama", "-o", str(tmp_path / "out.txt")])
    assert "Warning" not in result.output


def test_privacy_warning_suppressed_by_privacy_ack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("privacy_ack: true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "openai", "-o", str(tmp_path / "out.txt")])
    assert "Warning" not in result.output


def test_summarize_empty_transcript_exits(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.txt"
    transcript.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "ollama", "-o", str(tmp_path / "out.txt")])
    assert result.exit_code == 1
    assert "пуст" in result.output.lower()


def test_run_empty_transcription_saves_transcript_and_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "silent.wav"
    audio.write_bytes(b"\x00" * 16)
    transcript_file = tmp_path / "out.txt"
    summary_file = tmp_path / "summary.txt"

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Transcript

    empty_tr = Transcript(segments=())
    # Repo config.yaml uses the external openai provider; supply a dummy key.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: empty_tr)

    llm_called = [False]

    def should_not_be_called(self: object, text: str) -> str:
        llm_called[0] = True
        return "summary"

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", should_not_be_called)

    result = runner.invoke(
        app,
        [
            "run",
            str(audio),
            "--transcript",
            str(transcript_file),
            "--summary",
            str(summary_file),
        ],
    )

    assert result.exit_code == 1
    assert "распознана" in result.output.lower()
    assert transcript_file.exists(), "transcript must be saved even when empty"
    assert not llm_called[0], "LLM must not be called for empty transcript"


def test_transcribe_whisper_load_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"\x00" * 16)

    import providers.whisper as whisper_mod

    def bad_init(self: object, model_name: str = "large-v3") -> None:
        raise RuntimeError("CUDA not available")

    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", bad_init)
    result = runner.invoke(app, ["transcribe", str(audio)])
    assert result.exit_code == 1
    assert "Whisper model" in result.output


def test_batch_help() -> None:
    result = runner.invoke(app, ["batch", "--help"])
    assert result.exit_code == 0


def test_batch_missing_folder(tmp_path: Path) -> None:
    result = runner.invoke(app, ["batch", str(tmp_path / "nope")])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_batch_empty_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Repo config.yaml uses the external openai provider; supply a dummy key so
    # validation passes and we reach the "No audio files" branch.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")
    result = runner.invoke(app, ["batch", str(tmp_path)])
    assert result.exit_code == 0
    assert "No audio files" in result.output


def test_batch_output_naming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "meeting.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "call.mp3").write_bytes(b"\x00" * 16)

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)
    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary text")

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 0
    assert (tmp_path / "meeting.txt").exists()
    assert (tmp_path / "meeting_summary.txt").exists()
    assert (tmp_path / "call.txt").exists()
    assert (tmp_path / "call_summary.txt").exists()
    assert "2 succeeded, 0 failed" in result.output


def test_batch_output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "rec.wav").write_bytes(b"\x00" * 16)
    out_dir = tmp_path / "out"

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)
    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")

    result = runner.invoke(app, ["batch", str(audio_dir), "-o", str(out_dir), "-p", "ollama"])

    assert result.exit_code == 0
    assert (out_dir / "rec.txt").exists()
    assert (out_dir / "rec_summary.txt").exists()


def test_batch_partial_failure_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "good.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "bad.wav").write_bytes(b"\x00" * 16)

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Segment, Transcript

    good_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    def fake_transcribe(self: object, audio: Path, language: str = "ru", on_progress: object = None) -> Transcript:
        if audio.name == "bad.wav":
            raise RuntimeError("corrupt audio")
        return good_tr

    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", fake_transcribe)
    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 1
    assert "1 succeeded, 1 failed" in result.output
    assert (tmp_path / "good.txt").exists()
    assert (tmp_path / "good_summary.txt").exists()
    assert not (tmp_path / "bad_summary.txt").exists()


def test_batch_stem_collision_exits(tmp_path: Path) -> None:
    (tmp_path / "call.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "call.mp3").write_bytes(b"\x00" * 16)

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 1
    assert "collision" in result.output.lower()
    assert "call" in result.output


def test_batch_empty_transcript_skips_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "silent.wav").write_bytes(b"\x00" * 16)

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Transcript

    empty_tr = Transcript(segments=())
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: empty_tr)

    llm_called = [False]

    def should_not_be_called(self: object, text: str) -> str:
        llm_called[0] = True
        return "summary"

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", should_not_be_called)

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    # After ARCH-001 unification, empty transcription is a failure (matches run/run_one_file).
    assert result.exit_code == 1
    assert not llm_called[0]
    assert (tmp_path / "silent.txt").exists()  # transcript still written before the empty check
    assert not (tmp_path / "silent_summary.txt").exists()
    assert "0 succeeded, 1 failed" in result.output


def test_summarize_format_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")
    out = tmp_path / "out.txt"

    # Repo config.yaml uses the external openai provider; supply a dummy key.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary text")
    result = runner.invoke(app, ["summarize", str(transcript), "-f", "json", "-o", str(out)])
    assert result.exit_code == 0
    import json

    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["mode"] == "medium"
    assert data["summary"] == "summary text"


def test_summarize_format_json_stdout_is_pure_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """stdout must be parseable as JSON — status messages must go to stderr only."""
    import json

    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    # Repo config.yaml uses the external openai provider; supply a dummy key.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "clean summary")
    result = runner.invoke(app, ["summarize", str(transcript), "-f", "json"])
    assert result.exit_code == 0
    # result.stdout is pure stdout (Click 8 separates stdout/stderr)
    data = json.loads(result.stdout)
    assert data["summary"] == "clean summary"
    assert "Сохранено" in result.stderr


def test_summarize_unknown_format(tmp_path: Path) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello\n", encoding="utf-8")
    result = runner.invoke(app, ["summarize", str(transcript), "-f", "html"])
    assert result.exit_code == 1
    assert "format" in result.output.lower()


def test_summarize_llm_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    # Repo config.yaml uses the external openai provider; supply a dummy key.
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "test-key")

    import providers.llm as llm_mod

    def bad_summarize(self: object, text: str) -> str:
        raise ConnectionError("LLM endpoint unreachable")

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", bad_summarize)
    result = runner.invoke(app, ["summarize", str(transcript)])
    assert result.exit_code == 1
    assert "подключиться" in result.output.lower()


def test_summarize_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    import providers.llm as llm_mod
    import utils

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "summary")

    def bad_write(path: Path, text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(utils, "write_text_atomic", bad_write)
    result = runner.invoke(app, ["summarize", str(transcript), "-p", "ollama"])
    assert result.exit_code == 1
    assert "сохранить саммари" in result.output.lower()


def test_transcribe_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"\x00" * 16)

    import providers.whisper as whisper_mod
    import utils
    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)

    def bad_write(path: Path, text: str) -> None:
        raise OSError("no space left")

    monkeypatch.setattr(utils, "write_text_atomic", bad_write)
    result = runner.invoke(app, ["transcribe", str(audio), "-o", str(tmp_path / "out.txt")])
    assert result.exit_code == 1
    assert "Error writing" in result.output


def test_summarize_summary_language_unknown(tmp_path: Path) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")
    result = runner.invoke(app, ["summarize", str(transcript), "--summary-language", "en"])
    assert result.exit_code == 1
    assert "en" in result.output


def test_summarize_summary_language_ru(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = tmp_path / "t.txt"
    transcript.write_text("[00:00] hello world\n", encoding="utf-8")

    import providers.llm as llm_mod

    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "итог")
    result = runner.invoke(
        app,
        [
            "summarize",
            str(transcript),
            "-p",
            "ollama",
            "--summary-language",
            "ru",
        ],
    )
    assert result.exit_code == 0


def test_run_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"\x00" * 16)

    import providers.llm as llm_mod
    import providers.whisper as whisper_mod
    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=1.0, text="discussed roadmap"),))
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)
    monkeypatch.setattr(llm_mod.LLMSummarizer, "summarize", lambda self, text: "roadmap summary")

    transcript_out = tmp_path / "tr.txt"
    summary_out = tmp_path / "sum.txt"
    result = runner.invoke(
        app,
        [
            "run",
            str(audio),
            "--transcript",
            str(transcript_out),
            "--summary",
            str(summary_out),
            "-p",
            "ollama",
        ],
    )

    assert result.exit_code == 0
    assert transcript_out.exists()
    assert summary_out.exists()
    assert "roadmap summary" in summary_out.read_text(encoding="utf-8")


# ── preprocess command ────────────────────────────────────────────────────────


def test_preprocess_help() -> None:
    result = runner.invoke(app, ["preprocess", "--help"])
    assert result.exit_code == 0


def test_preprocess_missing_audio(tmp_path: Path) -> None:
    result = runner.invoke(app, ["preprocess", str(tmp_path / "nope.mp3")])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_preprocess_with_explicit_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "input.mp3"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"

    import preprocessing as prep_mod

    calls: list[tuple] = []

    def fake_preprocess(a, o, s):
        calls.append((a, o, s))
        return o

    monkeypatch.setattr(prep_mod, "preprocess_audio", fake_preprocess)

    result = runner.invoke(app, ["preprocess", str(audio), "-o", str(output)])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0][0] == audio
    assert calls[0][1] == output
    assert "Preprocessed audio saved to" in result.output


def test_preprocess_default_output_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"\x00" * 16)

    import preprocessing as prep_mod

    calls: list[tuple] = []

    def fake_preprocess(a, o, s):
        calls.append((a, o, s))
        return o

    monkeypatch.setattr(prep_mod, "preprocess_audio", fake_preprocess)

    result = runner.invoke(app, ["preprocess", str(audio)])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    expected_output = audio.with_name("meeting.preprocessed.wav")
    assert calls[0][1] == expected_output
    assert "meeting.preprocessed.wav" in result.output


def test_preprocess_runs_even_when_enabled_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"\x00" * 16)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  enabled: false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    import preprocessing as prep_mod

    calls: list[tuple] = []

    def fake_preprocess(a, o, s):
        calls.append((a, o, s))
        return o

    monkeypatch.setattr(prep_mod, "preprocess_audio", fake_preprocess)

    result = runner.invoke(app, ["preprocess", str(audio)])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1, "preprocess_audio must be called even when enabled=false"


def test_preprocess_config_settings_reach_preprocess_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"\x00" * 16)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "preprocessing:\n  sample_rate: 22050\n  channels: 1\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    import preprocessing as prep_mod
    from config import PreprocessingSettings

    captured: list[PreprocessingSettings] = []

    def fake_preprocess(a, o, s):
        captured.append(s)
        return o

    monkeypatch.setattr(prep_mod, "preprocess_audio", fake_preprocess)

    result = runner.invoke(app, ["preprocess", str(audio)])

    assert result.exit_code == 0, result.output
    assert captured[0].sample_rate == 22050
    assert captured[0].channels == 1


def test_preprocess_ffmpeg_error_exits_with_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"\x00" * 16)

    import preprocessing as prep_mod
    from preprocessing import PreprocessingError

    def fake_preprocess(a, o, s):
        raise PreprocessingError("ffmpeg failed: codec not found")

    monkeypatch.setattr(prep_mod, "preprocess_audio", fake_preprocess)

    result = runner.invoke(app, ["preprocess", str(audio)])

    assert result.exit_code == 1
    assert "Preprocessing error" in result.output
    assert "codec not found" in result.output


def test_transcribe_output_dir_uncreatable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # REL-008: a failing mkdir of the output directory must fail cleanly (exit 1),
    # not dump an OSError traceback past the error boundary.
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "forbidden" / "out.txt"

    def bad_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "mkdir", bad_mkdir)
    result = runner.invoke(app, ["transcribe", str(audio), "-o", str(output)])
    assert result.exit_code == 1
    assert "Error creating output directory" in result.output


def test_transcribe_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "rec.wav"
    audio.write_bytes(b"\x00" * 16)
    out = tmp_path / "out.txt"

    import providers.whisper as whisper_mod
    from transcript import Segment, Transcript

    fake_tr = Transcript(segments=(Segment(start=0.0, end=2.0, text="hello world"),))
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(whisper_mod.WhisperTranscriber, "transcribe", lambda self, audio, language="ru", on_progress=None: fake_tr)

    result = runner.invoke(app, ["transcribe", str(audio), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "hello world" in out.read_text(encoding="utf-8")
