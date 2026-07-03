from __future__ import annotations

import ctypes
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

from transcript import Segment, Transcript

logger = logging.getLogger(__name__)


def _set_cuda_paths() -> None:
    """Pre-load venv NVIDIA libs so ctranslate2's lazy dlopen calls find them."""
    if getattr(sys, "frozen", False):
        # Portable (PyInstaller) build: CUDA libs are NOT bundled (~1.9 GB). They are downloaded on
        # demand into cuda_support.cuda_libs_dir(); add them to PATH so ctranslate2's dlopen resolves
        # them. The isdir guards make a CPU-only run (libs not downloaded) harmless.
        from cuda_support import cuda_libs_dir  # noqa: PLC0415

        base = cuda_libs_dir()
        nvidia_dirs = [str(base / "nvidia" / "cublas" / "bin"), str(base / "nvidia" / "cudnn" / "bin")]
        existing = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join([d for d in nvidia_dirs if os.path.isdir(d)] + [existing])
        return

    project_root = Path(__file__).resolve().parents[2]
    if sys.platform == "win32":
        logger.info("windows detected, adding NVIDIA libs to PATH")
        site = project_root / ".venv" / "Lib" / "site-packages"
        lib_dir = "bin"
        env_var = "PATH"
        sep = ";"
        nvidia_dirs = [
            str(site / "nvidia" / "cublas" / lib_dir),
            str(site / "nvidia" / "cudnn" / lib_dir),
        ]
        existing = os.environ.get(env_var, "")
        os.environ[env_var] = sep.join(nvidia_dirs + [existing])
    else:
        logger.info("linux detected, adding NVIDIA libs to LD_LIBRARY_PATH")
        py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site = project_root / ".venv" / "lib" / py_ver / "site-packages"
        lib_dir = "lib"
        # Update LD_LIBRARY_PATH for child processes
        nvidia_dirs = [
            str(site / "nvidia" / "cublas" / lib_dir),
            str(site / "nvidia" / "cudnn" / lib_dir),
            str(site / "nvidia" / "cuda_nvrtc" / lib_dir),
        ]
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = ":".join(nvidia_dirs + [existing])
        # Pre-load libs via absolute path so ctranslate2's dlopen finds them already mapped.
        # glibc dlopen caches by SONAME; a full-path load satisfies later name-only lookups.
        for lib_path in [
            site / "nvidia" / "cublas" / lib_dir / "libcublasLt.so.12",
            site / "nvidia" / "cublas" / lib_dir / "libcublas.so.12",
            site / "nvidia" / "cudnn" / lib_dir / "libcudnn.so.9",
        ]:
            if lib_path.exists():
                ctypes.CDLL(str(lib_path))


class WhisperTranscriber:
    def __init__(
        self,
        model_name: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "default",
        beam_size: int = 5,
        vad_filter: bool = True,
        condition_on_previous_text: bool = True,
    ) -> None:
        # Portable build: GPU libs are downloaded on demand. Fail early with a clear message rather
        # than a cryptic ctranslate2 dlopen error when the user picked CUDA without downloading them.
        if getattr(sys, "frozen", False) and device == "cuda":
            from cuda_support import is_cuda_installed  # noqa: PLC0415

            if not is_cuda_installed():
                raise RuntimeError(
                    "Поддержка GPU не загружена. Скачайте её в «Настройки → Транскрибация» "
                    "или выберите устройство CPU."
                )
        _set_cuda_paths()
        from faster_whisper import WhisperModel  # noqa: PLC0415
        from rich.console import Console  # noqa: PLC0415

        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._condition_on_previous_text = condition_on_previous_text

        # "default": float16 for CUDA (fast, GPU-native); int8 for CPU/auto (CPU-compatible).
        if compute_type == "default":
            compute_type = "float16" if device == "cuda" else "int8"
            logger.info("compute_type resolved to %r for device=%r", compute_type, device)

        with Console(stderr=True).status(f"[bold cyan]Loading model {model_name}…[/]"):
            self._model = WhisperModel(model_name, device=device, compute_type=compute_type)
        logger.info("Model %s loaded on %s.", model_name, device)

    def transcribe(
        self, audio: Path, language: str = "ru", *, on_progress: Callable[[float], None] | None = None
    ) -> Transcript:
        from rich.console import Console  # noqa: PLC0415
        from rich.progress import (  # noqa: PLC0415
            BarColumn,
            Progress,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        logger.info("Transcribing %s…", audio)
        segments_iter, info = self._model.transcribe(
            str(audio),
            language=language,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            condition_on_previous_text=self._condition_on_previous_text,
        )
        with Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=Console(stderr=True),
            # The desktop bridge's on_progress callback writes NDJSON to sys.stdout; Rich's default
            # redirect_stdout=True would swallow those lines into the stderr console, so the app
            # never sees per-segment progress. stdout must stay untouched here.
            redirect_stdout=False,
        ) as progress:
            duration = info.duration
            if on_progress is not None and not duration:
                logger.warning("Whisper reported no audio duration — transcription progress %% unavailable.")
            task = progress.add_task("Transcribing", total=duration or None)
            segments = []
            for s in segments_iter:
                segments.append(Segment(start=s.start, end=s.end, text=s.text.strip()))
                if duration:
                    progress.update(task, completed=s.end)
                    if on_progress is not None:
                        on_progress(min(1.0, s.end / duration))

        logger.info("Got %d segments (duration=%.1fs).", len(segments), info.duration or 0.0)
        return Transcript(segments=tuple(segments))
