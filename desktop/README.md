# Recap Desktop

Tauri 2 + React + TypeScript + Vite + Tailwind + shadcn-style UI for the Recap
transcription/summarization workflow. Windows-first.

The UI never parses CLI output — it talks to the Python workflow through the JSON bridge
(`src/desktop_bridge.py`, exposed as the `recap-bridge` console script). The Rust layer
(`src-tauri`) only spawns that bridge and forwards `recap-progress` events to the webview.

## Architecture

```
React UI ──invoke──▶ Rust commands (src-tauri/src/lib.rs)
                         │ spawn + JSON stdin/stdout
                         ▼
                    recap-bridge  (src/desktop_bridge.py)
                         │
                         ▼
                    workflows.run_one_file  (src/workflows.py)
```

- One-shot commands (`get_settings`, `save_settings`, `set_api_key`, `delete_api_key`,
  `test_connection`, `get_history`, `delete_history_item`, `export_summary`, `read_text`)
  exchange a single JSON object.
- `run_recap` and `resummarize` stream newline-delimited JSON: each `{"type":"progress"}` line is
  re-emitted to the webview as a `recap-progress` event; the final `{"type":"result"}` line is returned.
- API keys are stored in the OS keychain via Python `keyring`; they never reach `config.yaml`,
  the history JSON, or the UI (only a masked "saved / not saved" state is shown).
- Desktop state (a dedicated `config.yaml` + `history.json`) lives in the Tauri app-data
  directory, passed to the bridge as `RECAP_DESKTOP_DATA_DIR`. The repo's own `config.yaml`
  is never touched.

## Frontend development (no Rust required)

`node`/`npm` only:

```bash
npm install
npm run dev      # Vite dev server on http://localhost:1420 (runs against the in-memory mock bridge)
npm run build    # tsc --noEmit && vite build
npm run lint
npm run test     # vitest
```

When not running inside a Tauri window, `src/lib/bridge.ts` falls back to an in-memory mock
so the whole UI (run, partial-success, settings, history, export) is demoable in a browser.

## Running the real desktop app (requires the Rust toolchain)

Prerequisites: Rust (`cargo`/`rustc`) and the Tauri 2 system deps (WebView2 on Windows), plus
the Python project installed so `recap-bridge` works (`uv sync` / `pip install -e .`).

Configure how Rust launches the bridge (defaults shown):

| Variable             | Purpose                                                        |
| -------------------- | -------------------------------------------------------------- |
| `RECAP_BRIDGE_BIN`   | Full path to an installed `recap-bridge` executable.           |
| `RECAP_PYTHON`       | Python exe used as `python -m desktop_bridge` (default `python`). |
| `RECAP_SRC`          | Path to the project's `src/` added to `PYTHONPATH`.            |

Example (PowerShell, dev against the repo venv):

```powershell
$env:RECAP_PYTHON = "$PWD\..\.venv\Scripts\python.exe"
$env:RECAP_SRC    = "$PWD\..\src"
npm run tauri dev
```

Generate the full icon set once from the chosen icon:

```bash
npm run tauri icon src/assets/recap-icon.png
```

## Verification status

Validated where it was run; environment-specific gaps are called out rather than glossed over.

- ✅ Python: `pytest` (298 tests), `ruff`, `mypy` — pass.
- ✅ `cargo check` — passes (compiled on Windows with the Rust toolchain).
- ✅ `npm run build` / `npm run lint` / `npm run test` — pass under the WSL dev shell
  (using Windows `node.exe`); `lint` reports 2 non-blocking `react-refresh` warnings.
- ⚠️ Known environment issue: under some Windows shells `npm run build` / `npm run test`
  can fail with `spawn EPERM` from esbuild — this is an esbuild/Windows process-spawn
  permission problem (often antivirus or a restricted shell), not a code error. The same
  commands succeed from the WSL shell and under a normal Windows terminal with esbuild's
  binary unblocked. If you hit it, run the commands from WSL or allow
  `node_modules/@esbuild/win32-x64/esbuild.exe` in your AV.
- The `src-tauri` layer is a thin, standard Tauri-2 subprocess spawner; all testable logic
  lives in Python (`src/desktop_bridge.py`, `src/workflows.py`).

> **`keyring`** must be installed in the active Python environment for API-key storage to
> work (`uv lock && uv sync`, or `pip install "keyring>=25.0"`). It is declared in
> `pyproject.toml`; settings load degrades gracefully if it is missing, but
> save/delete/test of keys requires it.
