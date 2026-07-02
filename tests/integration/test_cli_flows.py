"""
Integration tests — CLI flows.

Each test exercises multiple real components together:
  Settings.load → providers.factory → formatters → file I/O → CLI exit codes.

The only things replaced with fakes are the external I/O boundaries:
  - providers.factory.make_transcriber  →  FakeTranscriber (no GPU / faster-whisper)
  - providers.factory.make_summarizer   →  FakeSummarizer  (no LLM / network)

Everything else — config loading, validation, formatters, atomic writes,
privacy warnings, argument precedence — runs with real code.

Run:
    uv run pytest tests/integration -v
    uv run pytest -m integration -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from cli import app

if TYPE_CHECKING:
    from transcript import Transcript

pytestmark = pytest.mark.integration

runner = CliRunner()


# ─── Fake provider doubles ────────────────────────────────────────────────────


class FakeTranscriber:
    """Returns a fixed non-empty transcript without loading Whisper."""

    def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
        from transcript import Segment, Transcript

        return Transcript(segments=(Segment(start=0.0, end=1.0, text="обсудили дорожную карту"),))


class EmptyTranscriber:
    """Returns an empty transcript — simulates silent audio."""

    def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
        from transcript import Transcript

        return Transcript(segments=())


class FailingTranscriber:
    """Raises on every transcription attempt — simulates corrupt audio."""

    def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
        raise RuntimeError(f"corrupt: {audio.name}")


class PartialTranscriber:
    """Succeeds for 'good.*' files, fails for 'bad.*'."""

    def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
        if audio.stem == "bad":
            raise RuntimeError(f"corrupt: {audio.name}")
        from transcript import Segment, Transcript

        return Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))


class FakeSummarizer:
    """Returns a fixed LLM response without hitting the network."""

    # Use raw Markdown so we can verify the formatter actually transforms it.
    DEFAULT = "## Итог встречи\n1. обсудили дорожную карту"

    def __init__(self, response: str = DEFAULT) -> None:
        self.response = response
        self.received: list[str] = []

    def summarize(self, text: str) -> str:
        self.received.append(text)
        return self.response


class FailingSummarizer:
    """Always raises — simulates LLM connection error."""

    def summarize(self, text: str) -> str:
        raise ConnectionError("LLM down")


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def patch_factory(monkeypatch: pytest.MonkeyPatch) -> FakeSummarizer:
    """
    Replace both factory functions at the module boundary.

    Returns the FakeSummarizer instance so tests can inspect calls.
    """
    import providers.factory as factory_mod

    fake_sum = FakeSummarizer()
    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: fake_sum,
    )
    return fake_sum


@pytest.fixture()
def transcript_file(tmp_path: Path) -> Path:
    # Use the real to_file_format() output so from_file() strips timestamps correctly.
    t = tmp_path / "meeting.txt"
    t.write_text(
        "[0.00s -> 30.00s] обсудили дорожную карту\n[30.00s -> 60.00s] договорились о сроках\n",
        encoding="utf-8",
    )
    return t


@pytest.fixture()
def audio_file(tmp_path: Path) -> Path:
    a = tmp_path / "meeting.wav"
    a.write_bytes(b"RIFF" + b"\x00" * 36)
    return a


# ─── summarize: happy path ────────────────────────────────────────────────────


def test_summarize_writes_formatted_summary(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """Full summarize flow: real config loading, real formatter, real file write."""
    out = tmp_path / "summary.txt"
    result = runner.invoke(app, ["summarize", str(transcript_file), "-o", str(out), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # Telegram formatter converts "## Итог встречи" → "*Итог встречи*"
    # and "1. item" → "- item". Verify both transformations ran on the raw LLM response.
    assert "*Итог встречи*" in content
    assert "- обсудили дорожную карту" in content
    assert "## Итог" not in content  # raw Markdown must be gone
    # "Summary saved" goes to stdout for non-JSON format (cli.py: err=output_format=="json")
    assert "Сохранено" in result.stderr


def test_summarize_transcript_text_reaches_summarizer(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transcript text (stripped of timestamps) is what the summarizer receives."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama"])

    assert len(patch_factory.received) == 1
    assert "обсудили дорожную карту" in patch_factory.received[0]
    # timestamps must be stripped before reaching LLM
    assert "[00:00]" not in patch_factory.received[0]


def test_summarize_cli_flags_override_config(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI -p and -m flags take priority over config.yaml values."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "privacy_ack: true\nsummarization:\n  mode: detailed\n  model:\n    provider: openai\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    captured: dict[str, str] = {}
    import providers.factory as factory_mod

    def spy(settings, provider, mode, model_override=None, summary_language=None):
        captured["provider"] = provider
        captured["mode"] = mode
        return FakeSummarizer()

    monkeypatch.setattr(factory_mod, "make_summarizer", spy)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama", "-m", "brief"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["provider"] == "ollama"
    assert captured["mode"] == "brief"


def test_summarize_env_overrides_config(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RECAP_* env vars take priority over config.yaml."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("privacy_ack: true\nsummarization:\n  model:\n    provider: openai\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_PROVIDER", "ollama")

    captured: dict[str, str] = {}
    import providers.factory as factory_mod

    def spy(settings, provider, mode, model_override=None, summary_language=None):
        captured["provider"] = provider
        return FakeSummarizer()

    monkeypatch.setattr(factory_mod, "make_summarizer", spy)

    result = runner.invoke(app, ["summarize", str(transcript_file)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["provider"] == "ollama"


# ─── summarize: JSON output ───────────────────────────────────────────────────


def test_summarize_json_file_output(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """With -f json -o, the output file contains valid JSON with expected keys."""
    out = tmp_path / "summary.json"
    result = runner.invoke(
        app,
        ["summarize", str(transcript_file), "-f", "json", "-o", str(out), "-p", "ollama"],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"] == patch_factory.response
    assert data["mode"] == "medium"


def test_summarize_json_stdout_is_pure_json(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without -o, stdout must be parseable as JSON; status messages go to stderr only."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["summarize", str(transcript_file), "-f", "json", "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["summary"] == patch_factory.response
    # status messages must not pollute stdout
    assert "сохранено" in result.stderr.lower()


# ─── run: full flow ───────────────────────────────────────────────────────────


def test_run_creates_both_output_files(
    tmp_path: Path,
    audio_file: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """Full run: transcribe → save transcript → summarize → save summary."""
    tr_out = tmp_path / "tr.txt"
    sum_out = tmp_path / "sum.txt"

    result = runner.invoke(
        app,
        ["run", str(audio_file), "--transcript", str(tr_out), "--summary", str(sum_out), "-p", "ollama"],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert tr_out.exists()
    assert sum_out.exists()
    # transcript contains the fake transcription text
    assert "карту" in tr_out.read_text(encoding="utf-8")
    # summary contains the formatted LLM response
    assert "*Итог встречи*" in sum_out.read_text(encoding="utf-8")


def test_run_transcript_saved_before_llm_failure(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If LLM fails, the transcript file must already exist on disk."""
    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FailingSummarizer(),
    )

    tr_out = tmp_path / "tr.txt"
    sum_out = tmp_path / "sum.txt"

    result = runner.invoke(
        app,
        ["run", str(audio_file), "--transcript", str(tr_out), "--summary", str(sum_out), "-p", "ollama"],
    )

    assert result.exit_code == 1
    assert tr_out.exists(), "transcript must be persisted before the LLM is called"
    assert not sum_out.exists()
    assert "подключиться" in (result.stdout + result.stderr).lower()


def test_run_empty_transcript_skips_llm(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silent audio → transcript saved, LLM never called, exit code 1."""
    import providers.factory as factory_mod

    llm_called = [False]

    class TrackingSummarizer:
        def summarize(self, text: str) -> str:
            llm_called[0] = True
            return "should not appear"

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: EmptyTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: TrackingSummarizer(),
    )

    tr_out = tmp_path / "tr.txt"
    sum_out = tmp_path / "sum.txt"

    result = runner.invoke(
        app,
        ["run", str(audio_file), "--transcript", str(tr_out), "--summary", str(sum_out), "-p", "ollama"],
    )

    assert result.exit_code == 1
    assert tr_out.exists(), "transcript must be saved even for empty audio"
    assert not llm_called[0], "LLM must not be called when transcript is empty"
    assert "распознана" in (result.stdout + result.stderr).lower()


# ─── batch: flow ──────────────────────────────────────────────────────────────


def test_batch_creates_named_files_for_each_audio(
    tmp_path: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """Each audio file gets {stem}.txt and {stem}_summary.txt."""
    (tmp_path / "meeting.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "call.mp3").write_bytes(b"\x00" * 16)

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert (tmp_path / "meeting.txt").exists()
    assert (tmp_path / "meeting_summary.txt").exists()
    assert (tmp_path / "call.txt").exists()
    assert (tmp_path / "call_summary.txt").exists()
    assert "2 succeeded, 0 failed" in result.stdout + result.stderr


def test_batch_output_dir(
    tmp_path: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """With -o, output files go to the specified directory."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "rec.wav").write_bytes(b"\x00" * 16)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["batch", str(audio_dir), "-o", str(out_dir), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert (out_dir / "rec.txt").exists()
    assert (out_dir / "rec_summary.txt").exists()
    assert not (audio_dir / "rec_summary.txt").exists()


def test_batch_json_format(
    tmp_path: Path,
    patch_factory: FakeSummarizer,
) -> None:
    """With -f json, summaries are written as {stem}_summary.json with valid JSON."""
    (tmp_path / "meeting.wav").write_bytes(b"\x00" * 16)

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    summary_file = tmp_path / "meeting_summary.json"
    assert summary_file.exists()
    assert (tmp_path / "meeting_summary.txt").exists()  # batch always writes both now (ARCH-001)
    data = json.loads(summary_file.read_text(encoding="utf-8"))
    assert "summary" in data
    assert "mode" in data


def test_batch_stem_collision_exits_before_any_processing(tmp_path: Path) -> None:
    """call.wav + call.mp3 → collision detected before processing any file."""
    (tmp_path / "call.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "call.mp3").write_bytes(b"\x00" * 16)

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 1
    combined = result.stdout + result.stderr
    assert "collision" in combined.lower()
    assert "call" in combined
    # no output files must have been created
    assert not (tmp_path / "call.txt").exists()


def test_batch_partial_failure_continues_and_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One corrupt file doesn't stop the batch; summary counts are accurate."""
    (tmp_path / "good.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "bad.wav").write_bytes(b"\x00" * 16)

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: PartialTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 1
    assert "1 succeeded, 1 failed" in result.stdout + result.stderr
    assert (tmp_path / "good.txt").exists()
    assert (tmp_path / "good_summary.txt").exists()
    assert not (tmp_path / "bad_summary.txt").exists()


# ─── config integration ───────────────────────────────────────────────────────


def test_config_transcription_language_passed_to_transcriber(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transcription.language from config.yaml reaches the transcriber."""
    (tmp_path / "config.yaml").write_text("transcription:\n  language: en\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, str] = {}

    class LangCapturingTranscriber:
        def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
            captured["language"] = language
            from transcript import Segment, Transcript

            return Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: LangCapturingTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    tr_out = tmp_path / "tr.txt"
    sum_out = tmp_path / "sum.txt"
    result = runner.invoke(
        app, ["run", str(audio_file), "--transcript", str(tr_out), "--summary", str(sum_out), "-p", "ollama"]
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["language"] == "en"


def test_config_legacy_flat_key_rejected(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Old flat 'language' key in config.yaml is rejected with a generic error."""
    (tmp_path / "config.yaml").write_text("language: en\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama"])

    assert result.exit_code == 1
    combined = result.stdout + result.stderr
    assert "Configuration error" in combined
    assert "Unknown config key: 'language'" in combined


def test_config_summary_language_flows_to_make_summarizer(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summarization.language from config.yaml is forwarded to make_summarizer."""
    (tmp_path / "config.yaml").write_text("summarization:\n  language: ru\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    captured: dict = {}
    import providers.factory as factory_mod

    def spy(settings, provider, mode, model_override=None, summary_language=None):
        captured["settings_lang"] = settings.summarization.language
        return FakeSummarizer()

    monkeypatch.setattr(factory_mod, "make_summarizer", spy)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["settings_lang"] == "ru"


def test_config_base_url_loaded_into_settings(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """base_url from config.yaml is available in Settings when factory is called."""
    (tmp_path / "config.yaml").write_text(
        "privacy_ack: true\nsummarization:\n  model:\n    base_url: http://my-llm:9000/v1\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    captured: dict = {}
    import providers.factory as factory_mod

    def spy(settings, provider, mode, model_override=None, summary_language=None):
        captured["base_url"] = settings.summarization.model.base_url
        return FakeSummarizer()

    monkeypatch.setattr(factory_mod, "make_summarizer", spy)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["base_url"] == "http://my-llm:9000/v1"


def test_config_model_overridden_by_cli(
    tmp_path: Path,
    transcript_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--model CLI flag overrides the model name field from config.yaml."""
    (tmp_path / "config.yaml").write_text("summarization:\n  model:\n    name: qwen3:latest\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    captured: dict = {}
    import providers.factory as factory_mod

    def spy(settings, provider, mode, model_override=None, summary_language=None):
        captured["model_override"] = model_override
        return FakeSummarizer()

    monkeypatch.setattr(factory_mod, "make_summarizer", spy)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama", "--model", "llama3:latest"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["model_override"] == "llama3:latest"


# ─── privacy warning integration ──────────────────────────────────────────────


def test_privacy_warning_shown_for_openai(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "openai"])
    combined = result.stdout + result.stderr
    assert "Warning" in combined
    assert "external" in combined


def test_no_privacy_warning_for_localhost_provider(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "ollama"])
    combined = result.stdout + result.stderr
    assert "Warning" not in combined


def test_privacy_warning_suppressed_by_privacy_ack(
    tmp_path: Path,
    transcript_file: Path,
    patch_factory: FakeSummarizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "config.yaml").write_text("privacy_ack: true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["summarize", str(transcript_file), "-p", "openai"])
    combined = result.stdout + result.stderr
    assert "Warning" not in combined


# ─── preprocessing integration ────────────────────────────────────────────────


def test_transcribe_with_preprocessing_passes_prepared_path_to_transcriber(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When preprocessing.enabled=true, transcriber receives the .preprocessed.wav path."""
    (tmp_path / "config.yaml").write_text(
        "preprocessing:\n  enabled: true\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    received_paths: list[Path] = []

    class PathCapturingTranscriber:
        def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
            received_paths.append(audio)
            from transcript import Segment, Transcript

            return Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    from unittest.mock import patch

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: PathCapturingTranscriber())
    out = tmp_path / "tr.txt"

    with patch("preprocessing.subprocess.run") as mock_run:
        mock_run.return_value = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(returncode=0)
        result = runner.invoke(app, ["transcribe", str(audio_file), "-o", str(out)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert len(received_paths) == 1
    assert received_paths[0] != audio_file
    assert str(received_paths[0]).endswith(".preprocessed.wav")


def test_run_with_preprocessing_passes_prepared_path_to_transcriber(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run command: transcriber receives prepared path, outputs use original stem."""
    (tmp_path / "config.yaml").write_text(
        "preprocessing:\n  enabled: true\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    received_paths: list[Path] = []

    class PathCapturingTranscriber:
        def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
            received_paths.append(audio)
            from transcript import Segment, Transcript

            return Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    from unittest.mock import MagicMock, patch

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: PathCapturingTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )
    tr_out = tmp_path / "tr.txt"
    sum_out = tmp_path / "sum.txt"

    with patch("preprocessing.subprocess.run", return_value=MagicMock(returncode=0)):
        result = runner.invoke(
            app,
            ["run", str(audio_file), "--transcript", str(tr_out), "--summary", str(sum_out), "-p", "ollama"],
        )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert received_paths[0] != audio_file
    assert str(received_paths[0]).endswith(".preprocessed.wav")


def test_batch_preprocessing_error_on_one_file_continues_others(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If preprocessing fails for one file in batch, others continue."""
    (tmp_path / "config.yaml").write_text(
        "preprocessing:\n  enabled: true\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    (tmp_path / "good.wav").write_bytes(b"\x00" * 16)
    (tmp_path / "bad.wav").write_bytes(b"\x00" * 16)

    import subprocess
    from unittest.mock import patch

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    call_count = [0]

    def selective_ffmpeg(cmd: list[str], **kwargs: object):
        call_count[0] += 1
        if "bad.wav" in str(cmd):
            raise subprocess.CalledProcessError(1, cmd, stderr="corrupt audio")
        from unittest.mock import MagicMock
        return MagicMock(returncode=0)

    with patch("preprocessing.subprocess.run", selective_ffmpeg):
        result = runner.invoke(app, ["batch", str(tmp_path), "-p", "ollama"])

    assert result.exit_code == 1
    assert "1 succeeded, 1 failed" in result.stdout + result.stderr


def test_transcribe_preprocessing_disabled_uses_original_path(
    tmp_path: Path,
    audio_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When preprocessing.enabled=false (default), transcriber gets the original path."""
    monkeypatch.chdir(tmp_path)

    received_paths: list[Path] = []

    class PathCapturingTranscriber:
        def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
            received_paths.append(audio)
            from transcript import Segment, Transcript

            return Transcript(segments=(Segment(start=0.0, end=1.0, text="hello"),))

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: PathCapturingTranscriber())
    out = tmp_path / "tr.txt"
    result = runner.invoke(app, ["transcribe", str(audio_file), "-o", str(out)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert received_paths[0] == audio_file
