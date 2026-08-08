from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcript import Transcript


def _make_fake_faster_whisper(captured: dict):
    class FakeInfo:
        duration = 2.0

    class FakeSegment:
        start = 0.0
        end = 1.0
        text = " hello "

    class FakeWhisperModel:
        def __init__(self, model_name: str, device: str = "cuda", compute_type: str = "float16") -> None:
            captured.update(model_name=model_name, device=device, compute_type=compute_type)

        def transcribe(
            self, audio: str, language: str, beam_size: int, vad_filter: bool, condition_on_previous_text: bool
        ):
            captured.update(
                beam_size=beam_size,
                vad_filter=vad_filter,
                condition_on_previous_text=condition_on_previous_text,
            )
            return iter([FakeSegment()]), FakeInfo()

    fake_fw = MagicMock()
    fake_fw.WhisperModel = FakeWhisperModel
    return fake_fw


@pytest.fixture
def fake_faster_whisper(monkeypatch: pytest.MonkeyPatch) -> dict:
    captured: dict = {}
    monkeypatch.setitem(sys.modules, "faster_whisper", _make_fake_faster_whisper(captured))
    return captured


def test_model_init_params(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    WhisperTranscriber(model_name="medium", device="cpu", compute_type="int8")

    assert fake_faster_whisper["model_name"] == "medium"
    assert fake_faster_whisper["device"] == "cpu"
    assert fake_faster_whisper["compute_type"] == "int8"


def test_default_compute_type_resolves_to_float16_on_cuda(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    WhisperTranscriber(model_name="large-v3", device="cuda", compute_type="default")
    assert fake_faster_whisper["compute_type"] == "float16"


def test_default_compute_type_resolves_to_int8_on_cpu(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    WhisperTranscriber(model_name="large-v3", device="cpu", compute_type="default")
    assert fake_faster_whisper["compute_type"] == "int8"


def test_cpu_without_explicit_compute_type_resolves_to_int8(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    WhisperTranscriber(model_name="large-v3", device="cpu")
    assert fake_faster_whisper["compute_type"] == "int8"


def test_default_compute_type_resolves_to_int8_on_auto(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    WhisperTranscriber(model_name="large-v3", device="auto", compute_type="default")
    assert fake_faster_whisper["compute_type"] == "int8"


def test_transcribe_params(fake_faster_whisper: dict) -> None:
    from providers.whisper import WhisperTranscriber

    tr = WhisperTranscriber(
        model_name="small",
        beam_size=3,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    result = tr.transcribe(Path("test.wav"), "en")

    assert fake_faster_whisper["beam_size"] == 3
    assert fake_faster_whisper["vad_filter"] is False
    assert fake_faster_whisper["condition_on_previous_text"] is False
    assert isinstance(result, Transcript)
    assert len(result.segments) == 1
    assert result.segments[0].text == "hello"


def test_transcribe_on_progress_stdout_not_swallowed_by_rich(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The bridge's on_progress writes NDJSON to sys.stdout from inside the segment loop.

    Rich's Progress defaults to redirect_stdout=True, which reroutes those writes into its
    (stderr) console — the desktop app then never receives per-segment progress lines. This
    pins stdout staying untouched while the progress bar is live.

    Rich only redirects when it believes the console is a terminal — which is exactly the
    desktop-worker case on Windows (stderr → NUL reports isatty()=True), so force it here.
    """
    import io

    import rich.console

    from providers.whisper import WhisperTranscriber

    monkeypatch.setattr(rich.console.Console, "is_terminal", property(lambda self: True))

    class FakeInfo:
        duration = 10.0

    class FakeSegment:
        start, end, text = 0.0, 5.0, " hi "

    class FakeModel:
        def __init__(self, *a: object, **k: object) -> None: ...

        def transcribe(self, audio, language, beam_size, vad_filter, condition_on_previous_text):  # type: ignore[no-untyped-def]
            return iter([FakeSegment()]), FakeInfo()

    fake_fw = MagicMock()
    fake_fw.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)

    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)

    tr = WhisperTranscriber(model_name="small", device="cpu")
    tr.transcribe(tmp_path / "audio.wav", "ru", on_progress=lambda p: sys.stdout.write(f"pct={p}\n"))

    assert out.getvalue() == "pct=0.5\n"  # empty if Rich redirected stdout into its console
