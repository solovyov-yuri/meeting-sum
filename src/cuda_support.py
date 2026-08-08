"""On-demand CUDA runtime download for the portable build.

The portable build ships **without** the NVIDIA CUDA libs (~1.9 GB) — ctranslate2 runs on CPU out of
the box. GPU support is fetched on demand: the cuBLAS + cuDNN wheels are downloaded from PyPI and
their DLLs extracted into a writable cache dir, which ``providers.whisper._set_cuda_paths()`` adds to
PATH. Pure stdlib (no pip in the frozen app).

Versions are pinned to what the app was built against so the DLL SONAMEs match ctranslate2. Bump
these together with the pins in ``pyproject.toml``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

# (pypi package, exact version) — must match pyproject.toml and the frozen build.
CUDA_PACKAGES: list[tuple[str, str]] = [
    ("nvidia-cublas-cu12", "12.9.2.10"),
    ("nvidia-cudnn-cu12", "9.22.0.52"),
]

ProgressCallback = Callable[[int, int, str], None]  # (done_bytes, total_bytes, message)
CancelCheck = Callable[[], bool]  # returns True when the user requested cancellation


class DownloadCancelled(Exception):
    """Raised when an in-progress CUDA download is cancelled by the user."""


def _sentinel() -> Path:
    """Marker written as the LAST step of a successful download (the extract is not atomic — a kill
    mid-cuDNN can leave a partial DLL set, so we key completeness on this, not on individual DLLs)."""
    return cuda_libs_dir() / ".recap-cuda-complete"


def _expected_marker() -> str:
    return "\n".join(f"{pkg}=={ver}" for pkg, ver in CUDA_PACKAGES)


def cuda_libs_dir() -> Path:
    """Writable dir holding the downloaded CUDA libs (``<dir>/nvidia/{cublas,cudnn}/bin/*.dll``).

    ``RECAP_CUDA_DIR`` overrides; otherwise ``<RECAP_DESKTOP_DATA_DIR>/cuda`` (desktop) or
    ``~/.recap/cuda`` (CLI/dev). Both the downloader and ``_set_cuda_paths`` resolve it this way.
    """
    override = os.environ.get("RECAP_CUDA_DIR")
    if override:
        return Path(override)
    data = os.environ.get("RECAP_DESKTOP_DATA_DIR")
    if data:
        return Path(data) / "cuda"
    return Path.home() / ".recap" / "cuda"


def is_cuda_installed() -> bool:
    """True when GPU CUDA libs are available.

    Only the frozen (portable) build needs the on-demand download; a dev / installer build ships the
    CUDA libs in the venv, so it is always considered installed.
    """
    if not getattr(sys, "frozen", False):
        return True
    sentinel = _sentinel()
    # Sentinel present AND matching the pinned versions (a version bump re-offers the download).
    return sentinel.is_file() and sentinel.read_text(encoding="utf-8").strip() == _expected_marker()


def _resolve_win_wheel(pkg: str, version: str) -> tuple[str, int]:
    """Resolve the win_amd64 wheel URL (and size) for a pinned package via the PyPI JSON API."""
    api = f"https://pypi.org/pypi/{pkg}/{version}/json"
    with urllib.request.urlopen(api, timeout=30) as resp:  # noqa: S310 - fixed https PyPI host
        data = json.load(resp)
    for entry in data.get("urls", []):
        if entry.get("filename", "").endswith("win_amd64.whl"):
            return entry["url"], int(entry.get("size") or 0)
    raise RuntimeError(f"Не найден win_amd64 wheel для {pkg}=={version}")


def _extract_dlls(whl_path: Path, dest: Path) -> int:
    """Extract only ``nvidia/**/bin/*.dll`` members from a wheel into ``dest``. Returns DLL count."""
    count = 0
    with zipfile.ZipFile(whl_path) as zf:
        for name in zf.namelist():
            parts = name.split("/")
            if parts[0] == "nvidia" and "bin" in parts and name.endswith(".dll"):
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as out:
                    out.write(src.read())
                count += 1
    return count


def download_cuda_libs(on_progress: ProgressCallback | None = None, cancel: CancelCheck | None = None) -> Path:
    """Download the pinned cuBLAS+cuDNN wheels and extract their DLLs into ``cuda_libs_dir()``.

    Reports byte progress across both wheels via ``on_progress`` and polls ``cancel`` frequently;
    on cancel it raises ``DownloadCancelled`` (the sentinel stays absent, so it re-offers). Returns
    the cache dir on success.
    """

    def check_cancel() -> None:
        if cancel and cancel():
            raise DownloadCancelled

    dest = cuda_libs_dir()
    dest.mkdir(parents=True, exist_ok=True)
    _sentinel().unlink(missing_ok=True)  # invalidate until this download fully completes

    check_cancel()  # honour an immediate cancel before touching the network
    resolved = [(pkg, ver, *_resolve_win_wheel(pkg, ver)) for pkg, ver in CUDA_PACKAGES]
    total = sum(size for *_, size in resolved) or 0
    done = 0

    # The wheel is written into a temp dir and only read/deleted after its handle is closed: on
    # Windows a still-open file cannot be unlinked (WinError 32), which used to abort the download
    # right after the first package — leaving a half-extracted cache and no sentinel.
    with tempfile.TemporaryDirectory(prefix="recap-cuda-") as tmp_dir:
        for pkg, ver, url, _size in resolved:
            check_cancel()
            if on_progress:
                on_progress(done, total, f"Загрузка {pkg} {ver}…")
            tmp_path = Path(tmp_dir) / f"{pkg}-{ver}.whl"
            try:
                with (
                    urllib.request.urlopen(url, timeout=60) as resp,  # noqa: S310 - PyPI files host
                    tmp_path.open("wb") as tmp,
                ):
                    while chunk := resp.read(1 << 20):
                        check_cancel()
                        tmp.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(min(done, total), total, f"Загрузка {pkg} {ver}…")
                if on_progress:
                    on_progress(done, total, f"Распаковка {pkg}…")
                if _extract_dlls(tmp_path, dest) == 0:
                    raise RuntimeError(f"В пакете {pkg}=={ver} не найдено DLL — повторите загрузку")
            finally:
                tmp_path.unlink(missing_ok=True)

    _sentinel().write_text(_expected_marker(), encoding="utf-8")  # mark complete (last step)
    if on_progress:
        on_progress(total, total, "Готово")
    return dest
