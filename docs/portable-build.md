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
│   └── _internal/       # Python runtime + deps + CUDA libs (nvidia/*/bin)
└── WebView2Loader.dll   # if produced by the build
```
…plus `dist/portable/Recap-<version>-portable.zip`.

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

The script: `uv sync` → PyInstaller freeze (`packaging/recap-bridge.spec`) → `tauri build
--no-bundle` → assemble `dist/portable/Recap/` → zip. Useful flags for iterating:

- `-SkipBridge` — reuse the last frozen bridge (the slow step).
- `-SkipApp` — reuse the last app build.
- `-SkipDeps` — skip `uv sync`.
- `-Ffmpeg <path>` — copy an `ffmpeg.exe` into the folder (see below).

## Caveats

- **Size.** The CUDA runtime wheels (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) are large; expect the
  folder to be **~2–4 GB**. There is no way around this for GPU transcription.
- **CUDA is the fragile part.** The spec copies `…/site-packages/nvidia/{cublas,cudnn}/bin` into the
  bundle, and `providers.whisper._set_cuda_paths()` has a `frozen` branch that adds
  `<bundle>/nvidia/*/bin` to `PATH`. If GPU transcription fails in the portable build, confirm those
  DLLs actually landed in `recap-bridge/_internal/nvidia/*/bin`. A machine with no NVIDIA GPU falls
  back to CPU (set the transcription device to `cpu`/`auto` in Settings).
- **ffmpeg.** Full-mode preprocessing shells out to `ffmpeg`. The portable build does **not** bundle
  it by default — either have `ffmpeg` on `PATH`, or pass `-Ffmpeg <path>` and add the portable
  folder to `PATH`. Transcription-only runs don't need ffmpeg.
- **First run** still downloads the selected Whisper model (network required once), cached under the
  user profile like a normal install.
- **API keys** live in the Windows Credential Manager (keyring), same as an installed build — they
  are not part of the portable folder.

## Verification status

The build tooling here (spec, script, `bundled_bridge_path`, the frozen `_set_cuda_paths` branch) was
authored and compile-checked but **not run end-to-end** — freezing faster-whisper + CUDA with
PyInstaller is Windows/GPU-specific and typically needs a round or two of hidden-import / CUDA-path
tuning on the actual build machine. Treat the first `build-portable.ps1` run as the real integration
test.
