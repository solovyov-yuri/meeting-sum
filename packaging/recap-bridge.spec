# PyInstaller spec for the `recap-bridge` Python sidecar (one-dir).
#
# Freezes src/desktop_bridge.py + all deps (faster-whisper, ctranslate2, openai, keyring, …) plus
# the NVIDIA CUDA runtime DLLs into dist/recap-bridge/, which scripts/build-portable.ps1 copies next
# to the Tauri app. The app then runs it with no Python install (see docs/portable-build.md).
#
# Build from the repo root:  pyinstaller packaging/recap-bridge.spec  (with the project venv active)
#
# CUDA is the fragile part: the NVIDIA libs live in the venv at Lib/site-packages/nvidia/*/bin and
# are added here as data so providers.whisper._set_cuda_paths() (frozen branch) finds them at
# <bundle>/nvidia/*/bin. If GPU transcription fails in the portable build, verify those folders made
# it into dist/recap-bridge/_internal/nvidia/*/bin.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent  # packaging/ -> repo root
SRC = ROOT / "src"

# Resolve the active venv's site-packages to pick up the NVIDIA CUDA DLLs.
if sys.platform == "win32":
    _site = Path(sys.prefix) / "Lib" / "site-packages"
else:
    _site = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

# Bundle the CUDA runtime dirs verbatim so the frozen _set_cuda_paths() can add them to PATH.
cuda_datas = []
for pkg in ("cublas", "cudnn"):
    for sub in ("bin", "lib"):
        d = _site / "nvidia" / pkg / sub
        if d.is_dir():
            cuda_datas.append((str(d), f"nvidia/{pkg}/{sub}"))

datas = list(cuda_datas)
binaries = []
hiddenimports = [
    # keyring picks its backend at runtime; PyInstaller can't see it statically.
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.macOS",
    "win32ctypes.core",
    "win32timezone",
]

# faster-whisper / ctranslate2 ship data files + binaries that must be collected wholesale.
# faster_whisper + ctranslate2 are required; a failure there means a broken bundle — do not swallow.
for pkg in ("faster_whisper", "ctranslate2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
# Optional transitive deps: collect if present, but announce a skip loudly (a genuinely-needed one
# missing here yields a CPU-broken bundle that otherwise fails only at runtime).
for pkg in ("tokenizers", "onnxruntime"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # noqa: BLE001
        print(f"[recap-bridge.spec] WARNING: could not collect optional package {pkg!r}: {exc}")

hiddenimports += collect_submodules("openai")


a = Analysis(
    [str(SRC / "desktop_bridge.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="recap-bridge",
    console=True,  # bridge is a stdin/stdout worker; the Tauri shell spawns it with CREATE_NO_WINDOW
    disable_windowed_traceback=False,
    argv_emulation=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="recap-bridge",
)
