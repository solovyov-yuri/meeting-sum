from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from config import PreprocessingSettings

# Upper bound on ffmpeg runtime so a stuck process cannot hang the CLI forever.
FFMPEG_TIMEOUT_SECONDS = 3600


class PreprocessingError(RuntimeError):
    pass


def _build_cmd(audio: Path, output: Path, settings: PreprocessingSettings) -> list[str]:
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-i", str(audio),
        "-ac", str(settings.channels),
        "-ar", str(settings.sample_rate),
        "-c:a", settings.codec,
    ]

    filters: list[str] = []
    if settings.highpass_hz is not None:
        filters.append(f"highpass=f={settings.highpass_hz}")
    if settings.loudness_normalization:
        filters.append(
            f"loudnorm=I={settings.target_lufs}:TP={settings.true_peak_db}:LRA={settings.loudness_range}"
        )
    if filters:
        cmd += ["-af", ",".join(filters)]

    cmd.append(str(output))
    return cmd


def preprocess_audio(audio: Path, output: Path, settings: PreprocessingSettings) -> Path:
    """Run ffmpeg to convert audio to a stable WAV format. Returns output path."""
    cmd = _build_cmd(audio, output, settings)
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise PreprocessingError(
            "ffmpeg not found. Install ffmpeg and ensure it is on PATH."
        )
    except subprocess.TimeoutExpired as exc:
        raise PreprocessingError(
            f"ffmpeg timed out after {FFMPEG_TIMEOUT_SECONDS} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or str(exc)).strip()
        raise PreprocessingError(f"ffmpeg failed: {message}") from exc
    return output


@contextmanager
def prepared_audio(audio: Path, settings: PreprocessingSettings) -> Iterator[Path]:
    if not settings.enabled:
        yield audio
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".preprocessed.wav") as f:
        tmp = Path(f.name)

    try:
        preprocess_audio(audio, tmp, settings)
        yield tmp
    finally:
        if not settings.keep_temp:
            tmp.unlink(missing_ok=True)
