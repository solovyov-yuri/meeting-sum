import io
import zipfile
from pathlib import Path

import pytest

import cuda_support


def test_cuda_libs_dir_prefers_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path / "over"))
    monkeypatch.setenv("RECAP_DESKTOP_DATA_DIR", str(tmp_path / "data"))
    assert cuda_support.cuda_libs_dir() == tmp_path / "over"


def test_cuda_libs_dir_uses_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RECAP_CUDA_DIR", raising=False)
    monkeypatch.setenv("RECAP_DESKTOP_DATA_DIR", str(tmp_path / "data"))
    assert cuda_support.cuda_libs_dir() == tmp_path / "data" / "cuda"


def test_is_cuda_installed_true_when_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    # Dev/installer build: CUDA ships in the venv, always "installed".
    monkeypatch.setattr(cuda_support.sys, "frozen", False, raising=False)
    assert cuda_support.is_cuda_installed() is True


def test_is_cuda_installed_requires_completion_sentinel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cuda_support.sys, "frozen", True, raising=False)
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path))
    assert cuda_support.is_cuda_installed() is False
    # Partial download (DLLs present, no sentinel) must NOT count as installed.
    (tmp_path / "nvidia/cublas/bin").mkdir(parents=True)
    (tmp_path / "nvidia/cublas/bin/cublas64_12.dll").write_bytes(b"\x00")
    assert cuda_support.is_cuda_installed() is False
    # Sentinel with matching versions → installed.
    cuda_support._sentinel().write_text(cuda_support._expected_marker(), encoding="utf-8")
    assert cuda_support.is_cuda_installed() is True
    # Sentinel from a different version → re-offer (not installed).
    cuda_support._sentinel().write_text("nvidia-cublas-cu12==0.0.0", encoding="utf-8")
    assert cuda_support.is_cuda_installed() is False


def test_download_cancels_before_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # An immediate cancel raises DownloadCancelled and never resolves/hits the network; no sentinel.
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path))
    monkeypatch.setattr(cuda_support.sys, "frozen", True, raising=False)

    def boom(*a: object, **k: object) -> object:
        raise AssertionError("network must not be touched after cancel")

    monkeypatch.setattr(cuda_support, "_resolve_win_wheel", boom)
    with pytest.raises(cuda_support.DownloadCancelled):
        cuda_support.download_cuda_libs(cancel=lambda: True)
    assert cuda_support.is_cuda_installed() is False


def test_extract_dlls_only_takes_bin_dlls(tmp_path: Path) -> None:
    # A wheel-like zip with a bin DLL, an unrelated file, and dist-info — only the DLL is extracted.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("nvidia/cublas/bin/cublas64_12.dll", b"DLL")
        zf.writestr("nvidia/cublas/include/foo.h", b"header")
        zf.writestr("nvidia_cublas_cu12-1.2.3.dist-info/RECORD", b"record")
    whl = tmp_path / "pkg.whl"
    whl.write_bytes(buf.getvalue())

    dest = tmp_path / "out"
    n = cuda_support._extract_dlls(whl, dest)
    assert n == 1
    assert (dest / "nvidia/cublas/bin/cublas64_12.dll").read_bytes() == b"DLL"
    assert not (dest / "nvidia/cublas/include/foo.h").exists()


class _FakeResponse:
    """Minimal urlopen stand-in: a context manager serving `payload` in chunks."""

    def __init__(self, payload: bytes) -> None:
        self._buf = io.BytesIO(payload)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self._buf.close()

    def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


def _wheel_bytes(pkg_dir: str, dll: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"nvidia/{pkg_dir}/bin/{dll}", b"DLL")
    return buf.getvalue()


def test_download_extracts_all_packages_and_marks_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # End-to-end over a faked PyPI: every pinned package is extracted and the sentinel is written.
    # This also pins the Windows file-handle contract — the wheel must be closed before it is read
    # and deleted, or the download dies with WinError 32 after the first package.
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path / "cuda"))
    monkeypatch.setattr(cuda_support.sys, "frozen", True, raising=False)

    wheels = {"nvidia-cublas-cu12": _wheel_bytes("cublas", "cublas64_12.dll"), "nvidia-cudnn-cu12": _wheel_bytes("cudnn", "cudnn64_9.dll")}
    monkeypatch.setattr(cuda_support, "_resolve_win_wheel", lambda pkg, ver: (f"https://example.invalid/{pkg}", len(wheels[pkg])))
    monkeypatch.setattr(cuda_support.urllib.request, "urlopen", lambda url, timeout=0: _FakeResponse(wheels[url.rsplit("/", 1)[1]]))

    progress: list[tuple[int, int, str]] = []
    dest = cuda_support.download_cuda_libs(on_progress=lambda d, t, m: progress.append((d, t, m)))

    assert (dest / "nvidia/cublas/bin/cublas64_12.dll").is_file()
    assert (dest / "nvidia/cudnn/bin/cudnn64_9.dll").is_file()
    assert cuda_support.is_cuda_installed() is True
    assert progress[-1][2] == "Готово"


def test_download_cancelled_mid_stream_raises_cancelled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Cancelling once bytes are flowing must surface as DownloadCancelled (the desktop's
    # cooperative-cancel contract) — not as an OS error from cleaning up the half-written wheel.
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path / "cuda"))
    monkeypatch.setattr(cuda_support.sys, "frozen", True, raising=False)

    payload = _wheel_bytes("cublas", "cublas64_12.dll")
    monkeypatch.setattr(cuda_support, "_resolve_win_wheel", lambda pkg, ver: ("https://example.invalid/w", len(payload)))
    monkeypatch.setattr(cuda_support.urllib.request, "urlopen", lambda url, timeout=0: _FakeResponse(payload))

    calls = {"n": 0}

    def cancel_after_first_chunk() -> bool:
        calls["n"] += 1
        return calls["n"] > 2  # 1: before network, 2: before the read loop, 3+: inside it

    with pytest.raises(cuda_support.DownloadCancelled):
        cuda_support.download_cuda_libs(cancel=cancel_after_first_chunk)
    assert cuda_support.is_cuda_installed() is False


def test_download_rejects_a_wheel_without_dlls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A wheel that yields no DLL must fail loudly instead of leaving a "complete" empty cache.
    monkeypatch.setenv("RECAP_CUDA_DIR", str(tmp_path / "cuda"))
    monkeypatch.setattr(cuda_support.sys, "frozen", True, raising=False)

    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("nvidia_cublas_cu12-1.2.3.dist-info/RECORD", b"record")
    monkeypatch.setattr(cuda_support, "_resolve_win_wheel", lambda pkg, ver: ("https://example.invalid/w", 0))
    monkeypatch.setattr(cuda_support.urllib.request, "urlopen", lambda url, timeout=0: _FakeResponse(empty.getvalue()))

    with pytest.raises(RuntimeError, match="не найдено DLL"):
        cuda_support.download_cuda_libs()
    assert cuda_support.is_cuda_installed() is False
