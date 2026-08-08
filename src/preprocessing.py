from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from config import PreprocessingSettings

# Upper bound on ffmpeg runtime so a stuck process cannot hang the CLI forever.
FFMPEG_TIMEOUT_SECONDS = 3600

_FFMPEG_NAMES = ("ffmpeg.exe",) if os.name == "nt" else ("ffmpeg",)


class PreprocessingError(RuntimeError):
    pass


def _resolve_ffmpeg() -> str:
    """Return the ffmpeg to run: one shipped with the app if present, else the bare name.

    In the portable (PyInstaller) build the executable lives in ``<app>/recap-bridge/`` while an
    ffmpeg shipped with it sits next to the app executable one level up — a directory the OS does
    not search, so a bare ``ffmpeg`` would miss it. Falling back to the bare name keeps the normal
    case (a system ffmpeg on PATH) resolved by the OS exactly as before.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for directory in (exe_dir, exe_dir.parent):
            for name in _FFMPEG_NAMES:
                candidate = directory / name
                if candidate.is_file():
                    return str(candidate)
    return "ffmpeg"


def _build_cmd(audio: Path, output: Path, settings: PreprocessingSettings) -> list[str]:
    cmd = [
        _resolve_ffmpeg(), "-nostdin", "-y", "-i", str(audio),
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
