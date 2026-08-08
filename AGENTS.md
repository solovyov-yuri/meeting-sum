# AGENTS.md

This file provides guidance to coding agents (Codex, Claude Code, etc.) when working with code in
this repository. It is the **canonical** agent contract; `CLAUDE.md` imports it verbatim and adds
only Claude-Code-specific notes.

## Project overview

`recap` transcribes meeting audio via `faster-whisper` (CUDA) and generates a Telegram-formatted summary
using any OpenAI-compatible LLM (OpenAI, xAI, Ollama, lm-studio, vllm). It ships two front-ends over one
Python core: a **Typer CLI** and a **Tauri 2 + React desktop app** (Rust shell → `recap-bridge` Python
subprocess).

## Environment & commands

The project is cross-platform and is normally driven with `uv` (e.g. `uv run pytest -v`).

The development machine here is **Windows**, with the venv under `.venv\Scripts\` (reached from WSL as
`.venv/Scripts/`). From WSL, do **not** run `uv` — it rebuilds and corrupts the Windows venv. Run the venv's
executables directly; you may run tests/lint/types yourself this way:

```bash
.venv/Scripts/pytest.exe -v           # tests (append tests/integration for integration only)
.venv/Scripts/ruff.exe check src/     # lint  (ruff.exe format src/ to format)
.venv/Scripts/mypy.exe src/           # type check
.venv/Scripts/recap.exe <cmd> --help  # CLI; commands: transcribe, summarize, run, batch, preprocess
.venv/Scripts/recap-bridge.exe        # desktop JSON bridge entry point (driven by the Tauri shell)
```

Desktop front-end (`desktop/`) checks, runnable from WSL against the Windows Node
(`/mnt/c/Program Files/nodejs/node.exe`):

```bash
cd desktop
npm run lint          # eslint
npm run test          # vitest
npm run build         # tsc --noEmit && vite build
```

**Verification boundary (WSL vs Windows).** From this WSL shell you CAN run: the Python tools above;
`npm run lint|test|build`; and the **Windows Rust toolchain** via `/mnt/c/Users/solov/.cargo/bin/cargo.exe`
— `cargo.exe check` and `cargo.exe clippy` on `desktop/src-tauri` compile and lint the Rust in ~5s
(deps are cached in `target/`). So a Rust change CAN be checked for compile/lint errors here — do it, don't
assume you can't. The *pipeline* is runnable here too — see "Desktop runtime debugging" below; it is the GPU
that isn't. What you CANNOT do here: actually run the GUI (`npm run tauri dev`, `tauri build`, launching
the app) or CUDA transcription — those need the user on Windows (PowerShell), output pasted back. So: Rust
*compilation* is verifiable by you; Rust *runtime behaviour* (e.g. cancel actually stops a run, no console
window flashes) stays **unverified until the user runs the app**.

**Desktop runtime debugging.** When the desktop pipeline misbehaves, in this order:

1. **Read the bridge log first** — `/mnt/c/Users/solov/AppData/Roaming/app.recap.desktop/logs/` is
   plain-readable from WSL. Start with `recap-bridge-serve.log`: the persistent worker runs the
   transcription and summarization, so that is where a failed run lands. `recap-bridge.log` holds the
   spawn-per-call commands (settings, export, history). They are separate files because a rotation
   cannot rename a file the other process holds open. Skipping the log once cost several "fixed →
   still broken" rounds.
2. **Reproduce the run from WSL**, no GUI needed: drive `desktop_bridge serve` as a subprocess with the
   venv python, `RECAP_DESKTOP_DATA_DIR` pointing at a scratch dir holding its own `config.yaml`
   (`model: tiny`, `device: cpu`). Real transcription does run this way.
3. Two traps: **env vars do not cross WSL → Windows** — set them inside the driver script, not in the
   shell; and the Windows **NUL device reports `isatty() = True`**, so a null stderr looks like a
   terminal to libraries that redirect on that signal (this is what once swallowed progress output).
4. Windows process inspection works from here: `tasklist.exe`, `powershell.exe Get-CimInstance Win32_Process`.

**Honesty about verification.** Never claim a check passed unless you actually ran it in this session. If a
check is impossible here (Rust/Tauri build, GPU transcription, a live LLM endpoint), say so explicitly and
list what you did verify and what remains unverified. A false "verified" is worse than an honest gap. (See
`docs/desktop-agent-checklist.md`.) Saying it once is not enough: add a line to
`docs/manual-qa-pending.md` (what you changed → how to check it) so the debt accumulates somewhere the
user can work through, instead of being remembered only by whoever wrote it.

**Docs are part of the change.** If you change behaviour this file, `docs/desktop-bridge-contract.md`,
`docs/desktop-tauri-spec.md` or the README describe, update that document in the same change. A contract
that outlives the code it describes is worse than no contract: the next agent obeys it.

**Git:** never commit, create branches, or make other git changes without an explicit request from the user.

## Architecture

```
src/
├── cli.py            # Typer CLI: per-command orchestration + I/O; the CLI error boundary
├── workflows.py      # provider-agnostic pipeline shared by CLI and desktop; run_one_file /
│                     #   resummarize_one return a RunResult (cancelled/partial_success/…) — a boundary
├── desktop_bridge.py # JSON facade + `recap-bridge` entry point; get/save settings, run/resummarize
│                     #   (streaming NDJSON), history, export, secrets — the desktop error boundary
├── secrets_store.py  # API keys in the OS keychain (keyring); never in config.yaml / history / logs
├── config.py         # nested frozen Settings dataclasses + Settings.load() (yaml → env, strict validation)
├── transcript.py     # Segment + Transcript (frozen); from_file / to_text / to_file_format
├── formatters.py     # render from the structured MeetingSummary: render_markdown/to_plain/to_html/
│                     #   to_json + parse_summary()/parse_plain() (text→object, the edit/export path)
├── models.py         # MeetingSummary / Section / Action — structured summary, the single source of truth
├── summary_schema.py # JSON schema for response_format + parse_summary_json() (LLM JSON → MeetingSummary)
├── utils.py          # write_text_atomic()
├── preprocessing.py  # preprocess_audio() + prepared_audio() context manager (ffmpeg)
├── prompts.py        # PROMPTS[lang][mode] + CHUNK_PROMPTS + JSON_PROMPTS[lang][mode]; get_prompt()
├── cuda_support.py   # portable build: NVIDIA GPU detection (ctypes, driver only) + on-demand CUDA
│                     #   runtime download (pure stdlib, no pip): pinned cuBLAS/cuDNN wheels →
│                     #   sha256-verified DLL cache that whisper._set_cuda_paths() uses
├── ollama_support.py # Ollama-only model presence check + streaming pull for the desktop
│                     #   "model not installed" flow (pure stdlib, native /api/* endpoints)
└── providers/
    ├── factory.py    # make_summarizer() / make_transcriber() — the single provider wiring point
    ├── whisper.py    # WhisperTranscriber (lazy faster_whisper import after CUDA path setup)
    └── llm.py        # LLMSummarizer (OpenAI-compatible client, streaming, chunking/truncation)

desktop/              # Tauri 2 desktop app
├── src/              # React + TypeScript UI; src/lib/bridge.ts is the single bridge entry (getBridge),
│                     #   with an in-memory mock so the whole UI is demoable in a browser without Rust/GPU
└── src-tauri/        # Rust shell: ~12 thin commands that spawn `recap-bridge` and stream its NDJSON

tests/                # test_*.py per non-trivial module + integration/test_cli_flows.py
```

`src/` is the Python path root (`pythonpath = ["src"]`, hatchling `sources = {"src" = ""}`). Tests: roughly
one `test_*.py` per module (trivial modules like `models`/`prompts` have none). The "mocks only at the
factory boundary" rule is the standard for the **integration** suite (`tests/integration/`); unit tests may
patch deeper (e.g. provider classes) as needed.

## Configuration

Resolution order: **CLI flags > env vars > config.yaml > defaults**.

The schema is **nested**: top-level paths + `privacy_ack`, plus `transcription`, `summarization`, and
`preprocessing` sections. `transcription` and `summarization` each hold a `model` sub-section. Validation is
strict — any unknown key (including old flat keys) raises `ConfigError`.

- **Full template:** `config.yaml.example`. Don't reproduce it here.
- **Env vars:** `RECAP_` + the upper-snake-cased nested path (e.g. `summarization.model.num_ctx` →
  `RECAP_SUMMARIZATION_MODEL_NUM_CTX`). The authoritative list is the `_ENV_*` maps in `config.py`.
  There is no `OPENAI_API_KEY` fallback — set `summarization.model.api_key` /
  `RECAP_SUMMARIZATION_MODEL_API_KEY`. An external provider (openai/xai) with no configured key raises a
  clear error in the factory; recap never silently uses the SDK's ambient `OPENAI_API_KEY`.

Non-obvious semantics:
- `summarization.language` defaults to `null` → the factory uses `"ru"`. It does **not** inherit
  `transcription.language`, so English audio still yields a Russian summary unless set explicitly.
- `summarization.max_transcript_chars` is the per-request LLM limit. `chunking_mode: chunk` splits long
  transcripts and merges per-chunk summaries; `truncate` cuts at the last newline before the limit.
- `summarization.model.num_ctx` is Ollama's `options.num_ctx`; ignored by OpenAI/xAI.
- `summarization.mode`: `brief` (2–3 sentences) | `medium` (topic + discussions + decisions) |
  `detailed` (participants + timeline + tasks with owners) | `lecture` (a study summary of a talk,
  not meeting minutes). The authoritative list is `SUMMARY_MODES` in `prompts.py`.

## Key design rules

- **Strict nested config.** `Settings` and all sub-sections are `frozen=True`. `Settings.load()` rejects unknown
  keys; there is no silent remapping of legacy keys.
- **Factory is the only wiring point.** CLI and desktop bridge call `make_summarizer()` / `make_transcriber()`
  and never construct providers directly. The factory validates provider/mode/language, resolves base URL,
  requires a key for external providers, and picks prompts.
- **Error boundaries (not just the CLI).** Providers and helpers let exceptions propagate; the boundaries that
  catch them are: `cli.py` (each command → `typer.Exit(code=1)`); `workflows.run_one_file` /
  `resummarize_one` (catch at step boundaries and return a `RunResult` with a status, powering the desktop
  `partial_success` / `cancelled` flows); and `desktop_bridge._streaming` / `main` (translate to NDJSON
  `error` lines — the `# noqa: BLE001 - boundary` sites). Do **not** "let exceptions fly" in workflows: it
  would break the bridge's partial-success contract.
- **CLI ↔ desktop divergence.** `run`/`summarize`/`batch` do route through `workflows.run_one_file` /
  `resummarize_one`, but the CLI owns what surrounds them: its own English messages and exit codes, and
  `--format` deciding what it echoes, while the desktop uses the Russian `RunResult` messages. The
  summary `.txt` form is a per-caller argument (`summary_format`): Markdown for the CLI, plain text for
  the desktop. This divergence is intentional and documented (`docs/desktop-tauri-spec.md` §4 / roadmap
  ARCH-001) — do not "unify" it without an explicit i18n + output-semantics decision from the owner.
- **Cooperative cancellation.** The desktop cancel is a flag file (path passed in the bridge payload), polled
  by `run_one_file` between steps; it returns a real `RunResult("cancelled")`. The Rust shell must not kill
  the bridge process (see `docs/desktop-bridge-contract.md` §6).
- **Lazy imports.** `cli.py` imports `providers.*` inside command bodies, so `recap --help` stays instant (no CUDA load).
- **CUDA paths.** `whisper._set_cuda_paths()` must prepend the `.venv` NVIDIA lib dirs before the `from faster_whisper import` line.
- **Atomic writes.** All file output goes through `utils.write_text_atomic()` — never `Path.write_text()` in production code.
- **Secrets.** API keys live only in the OS keychain (`secrets_store.py`); they must never reach `config.yaml`,
  `history.json`, or logs. The UI shows only a masked boolean.
- **LLM streaming.** `LLMSummarizer.summarize()` streams tokens to stderr and returns the full string
  (raw text, or JSON when `structured=True`). It stays "dumb": validation/parsing live above it.
- **Structured summary pipeline.** The `MeetingSummary` object is the single source of truth for all
  formats. `workflows._generate_summary()` tries JSON generation (`response_format`, modes in
  `JSON_PROMPTS` only) → `parse_summary_json`. `LLMSummarizer` asks for `SUMMARY_JSON_SCHEMA` first
  and retries once with plain `json_object` if the server refuses that `response_format` (so a
  refusal costs two provider calls); any failure after that (invalid JSON, schema mismatch) falls
  back to the text prompt + `formatters.parse_summary`. The
  editable form depends on the front-end (`summary_format`): the desktop writes/edits Telegram-ready
  plain text (`to_plain` ↔ `parse_plain`), the CLI keeps Markdown (`render_markdown` ↔
  `parse_summary`). Saving and exporting re-parse the possibly-edited text through
  `parse_summary_text`, which sniffs which of the two it is — so both parsers are permanent and each
  render/parse round-trip must stay exact.
- **Immutable transcript.** `Transcript.segments` is `tuple[Segment, ...]`.
- **Preprocessing.** The `preprocess` command always runs ffmpeg (ignores `enabled`, since invoking it is itself
  the request); `transcribe`/`run`/`batch` use `prepared_audio()`, which respects `enabled`.

Extending:
- **New OpenAI-compatible provider:** add its preset URL to `PROVIDER_PRESETS` in `config.py` — nothing else changes.
- **New summary mode:** add prompt constants in `prompts.py`, register under `PROMPTS["ru"][name]`, add the name to `SUMMARY_MODES`. Optionally add a JSON prompt under `JSON_PROMPTS["ru"][name]` to enable structured generation for it (else it uses the text path).
- **New summary language:** add constants in `prompts.py`, register under `PROMPTS["<lang>"]` and `CHUNK_PROMPTS["<lang>"]`; config validation picks it up automatically.
