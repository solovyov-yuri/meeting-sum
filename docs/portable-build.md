# Portable build (Windows, no-install)

Recap is a Tauri shell over a Python bridge (`recap-bridge`). The portable build freezes that bridge
into a standalone folder and ships it next to the app executable, so the target machine needs **no
Python install** — just unzip and run `Recap.exe`.

## Output

```
dist/portable/Recap/
├── Recap.exe            # the Tauri app
├── recap-bridge/        # frozen Python sidecar (PyInstaller one-dir)
│   ├── recap-bridge.exe
│   └── _internal/       # Python runtime + deps (NO CUDA — ~400 MB)
├── ffmpeg.exe           # optional, only with -Ffmpeg (see Caveats)
└── WebView2Loader.dll   # if produced by the build
```
…plus `dist/portable/Recap-<version>-portable.zip`.

The base folder is **~400 MB**: the NVIDIA CUDA runtime (~1.9 GB) is **not** bundled — CPU
transcription works out of the box, and GPU support is downloaded on demand from the app (see below).

The app locates the sidecar automatically: `desktop/src-tauri/src/lib.rs` (`bundled_bridge_path`)
looks for `recap-bridge/recap-bridge.exe` **next to `Recap.exe`**. No environment variables are
needed. (Dev runs still fall back to `RECAP_PYTHON -m desktop_bridge`; `RECAP_BRIDGE_BIN` overrides
everything.)

## Build it

Prerequisites on the Windows build machine: **uv**, **Node.js**, the **Rust toolchain**, and (for the
frozen bridge) the project venv synced. Then, from the repo root in PowerShell:

```powershell
pwsh -File scripts\build-portable.ps1
```

The script: `uv sync --group packaging` → PyInstaller freeze (`packaging/recap-bridge.spec`) → `tauri build
--no-bundle` → assemble `dist/portable/Recap/` → zip. Useful flags for iterating:

- `-SkipBridge` — reuse the last frozen bridge (the slow step).
- `-SkipApp` — reuse the last app build.
- `-SkipDeps` — skip `uv sync --group packaging` (PyInstaller must already be in the venv).
- `-Ffmpeg <path>` — copy an `ffmpeg.exe` into the folder (see below).

## GPU support (downloaded on demand)

To keep the download small, the portable build ships CPU-only. GPU (CUDA) support is fetched once,
automatically:

- Before anything is downloaded, `workflows._ensure_cuda` asks the machine whether it *has* an NVIDIA
  GPU (`cuda_support.detect_nvidia_gpu()` — a ctypes `cuInit`/`cuDeviceGetCount` against the driver's
  `nvcuda.dll`, no subprocess, no extra dependency):
  - **no card + device `cuda`** → the run fails immediately with a message telling the user to switch
    the device to `cpu`/`auto`; the ~2 GB download never starts (it could only end in a CUDA error);
  - **no card + device `auto`** → the run continues on CPU, but says so out loud: a `warning`
    event on the `transcribe` step (and a log line), so a slow CPU run is never silent;
  - **detection unavailable** (unexpected driver ABI) → nothing is blocked, the run behaves exactly
    as it did before and the log says the check was inconclusive. `RECAP_ASSUME_GPU=1` (or `0`)
    forces the answer if the probe ever misfires on an exotic setup.
- The **first run with device `cuda`** (GPU present and CUDA not yet present) runs a **`download`
  step** before transcription — `workflows._ensure_cuda` downloads the pinned `nvidia-cublas-cu12` +
  `nvidia-cudnn-cu12` wheels from PyPI (`src/cuda_support.py`) and extracts their DLLs into
  `<app data>/cuda/nvidia/*/bin`. It streams byte progress as a normal progress ring and the run's
  **Stop** button cancels it mid-download (leaving no completion sentinel → it re-offers next time).
- `providers.whisper._set_cuda_paths()` (frozen branch) adds that dir to `PATH` so ctranslate2 finds
  the libs. A version-stamped sentinel (`<cuda dir>/.recap-cuda-complete`) marks a *complete*
  download, so a killed one never reports installed.
- The pinned versions in `cuda_support.CUDA_PACKAGES` must match `pyproject.toml` (the DLL SONAMEs
  must match ctranslate2). Bump them together.
- Prefer CPU? Set the device to `cpu` in Settings — no download happens.
- **`auto` on a machine that HAS a card is not a CPU shortcut.** ctranslate2 picks the device from
  the driver alone (`get_cuda_device_count()` works without cuBLAS), so `auto` selects CUDA and then
  fails at the first matmul with `Library cublas64_12.dll is not found or cannot be loaded` while the
  libs are not downloaded (verified in the dev venv with the NVIDIA dirs off `PATH`). `auto` therefore
  currently means "CPU" only on GPU-less machines; on a GPU machine use `cuda` (which downloads the
  libs) or `cpu`. Making `auto` offer the download — or fall back to CPU — is an open product
  decision.

## Caveats
- **ffmpeg.** Full-mode preprocessing shells out to `ffmpeg`. The portable build does **not** bundle
  it by default — either have `ffmpeg` on `PATH`, or pass `-Ffmpeg <path>` at build time. A copy
  placed that way is picked up automatically, with no `PATH` edit: in a frozen build
  `preprocessing._resolve_ffmpeg()` looks for `ffmpeg.exe` next to the bridge executable and next to
  `Recap.exe` before falling back to the bare `ffmpeg` (i.e. to a system install on `PATH`).
  Transcription-only runs don't need ffmpeg.
- **First run** still downloads the selected Whisper model (network required once), cached under the
  user profile like a normal install.
- **API keys** live in the Windows Credential Manager (keyring), same as an installed build — they
  are not part of the portable folder.

## Verification status

The deterministic parts are tested here (`cuda_support` dir/marker/extract logic; the Rust and Python
plumbing compiles and passes the full pytest suite + lint + types). But the parts that only exist at runtime on
Windows are **unverified from this environment**: the PyInstaller freeze (hidden imports may need
tuning), the actual GPU CUDA download + dlopen, the packaged exe launching the bundled bridge, and
the bundled-ffmpeg pickup against a real `-Ffmpeg` build (its resolution logic is unit-tested with a
faked frozen layout, but never exercised on an assembled folder).
Treat the first `build-portable.ps1` run — and the first GPU download from Settings — as the real
integration tests.
