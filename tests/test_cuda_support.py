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
