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

- The **first run with device `cuda`** (and CUDA not yet present) runs a **`download` step** before
  transcription — `workflows._ensure_cuda` downloads the pinned `nvidia-cublas-cu12` +
  `nvidia-cudnn-cu12` wheels from PyPI (`src/cuda_support.py`) and extracts their DLLs into
  `<app data>/cuda/nvidia/*/bin`. It streams byte progress as a normal progress ring and the run's
  **Stop** button cancels it mid-download (leaving no completion sentinel → it re-offers next time).
- `providers.whisper._set_cuda_paths()` (frozen branch) adds that dir to `PATH` so ctranslate2 finds
  the libs. A version-stamped sentinel (`<cuda dir>/.recap-cuda-complete`) marks a *complete*
  download, so a killed one never reports installed.
- The pinned versions in `cuda_support.CUDA_PACKAGES` must match `pyproject.toml` (the DLL SONAMEs
  must match ctranslate2). Bump them together.
- Prefer CPU or unsure? Set the device to `cpu`/`auto` in Settings — no download happens.

## Caveats
- **ffmpeg.** Full-mode preprocessing shells out to `ffmpeg`. The portable build does **not** bundle
  it by default — either have `ffmpeg` on `PATH`, or pass `-Ffmpeg <path>` and add the portable
  folder to `PATH`. Transcription-only runs don't need ffmpeg.
- **First run** still downloads the selected Whisper model (network required once), cached under the
  user profile like a normal install.
- **API keys** live in the Windows Credential Manager (keyring), same as an installed build — they
  are not part of the portable folder.

## Verification status

The deterministic parts are tested here (`cuda_support` dir/marker/extract logic; the Rust and Python
plumbing compiles and passes the full pytest suite + lint + types). But the parts that only exist at runtime on
Windows are **unverified from this environment**: the PyInstaller freeze (hidden imports may need
tuning), the actual GPU CUDA download + dlopen, and the packaged exe launching the bundled bridge.
Treat the first `build-portable.ps1` run — and the first GPU download from Settings — as the real
integration tests.
