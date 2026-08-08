"""JSON/IPC-friendly facade over the Recap workflow for the Tauri desktop app.

The frontend never parses CLI stdout. Instead the Rust side spawns this module
(``recap-bridge <command>``), writes a JSON payload on stdin, and reads JSON on stdout.
For ``run_recap`` the process streams newline-delimited JSON: one ``{"type":"progress"}``
line per :class:`workflows.ProgressEvent`, then a final ``{"type":"result"}`` line.

Secrets are stored in the OS keychain via :mod:`secrets_store` and are never written to
``config.yaml``, the history JSON, or any log. Desktop state (config + history) lives under
``RECAP_DESKTOP_DATA_DIR`` (set by the Tauri app to its app-data directory).
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import os
import sys
import uuid
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from providers.whisper import WhisperTranscriber

import secrets_store
import workflows
from config import PROVIDER_PRESETS, Settings
from utils import write_text_atomic
from workflows import RunOptions

logger = logging.getLogger(__name__)

# The desktop shows, edits and copies the summary as Telegram-ready plain text, so that is the form
# the run writes to the .txt and hands to the UI (the CLI keeps Markdown). Editing round-trips
# through ``formatters.parse_plain``; every export is still rendered from the structured .json.
DESKTOP_SUMMARY_FORMAT = "plain"


# ── Desktop state locations ──────────────────────────────────────────────────────


def _force_utf8_io() -> None:
    """Make stdin/stdout/stderr UTF-8 regardless of the OS locale.

    Belt-and-suspenders alongside the Rust shell's ``PYTHONUTF8=1``: on Windows a piped stdout/stderr
    otherwise defaults to cp1252, and writing Cyrillic/CJK (the JSON result, streamed LLM tokens)
    crashes with "'charmap' codec can't encode". The incoming payload is UTF-8 JSON too, so stdin gets
    the same treatment — a locale-decoded stdin turns a Cyrillic ``audio_path`` into mojibake (cp1251)
    or fails to decode at all (cp1252). Covers direct/CLI invocation where the env is unset. Must run
    before the first read: ``reconfigure`` refuses to change the encoding of an already-read stream.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):  # pragma: no cover - stream not reconfigurable
                pass


def _data_dir() -> Path:
    env = os.environ.get("RECAP_DESKTOP_DATA_DIR")
    if env:
        base = Path(env)
    else:  # pragma: no cover - platform fallback, exercised via env in tests
        appdata = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
        base = Path(appdata) / "recap" if appdata else Path.home() / ".recap"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _configure_logging() -> None:
    """Bridge logging: warnings+ to stderr (plain), and full detail to a rotating log file in the
    data dir (ARCH-004). Field problems (CUDA/keyring/LLM tracebacks from ``logger.exception``)
    thus land somewhere inspectable. Logging setup must never break the bridge itself.
    """
    from logging.handlers import RotatingFileHandler  # noqa: PLC0415

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setLevel(logging.WARNING)
    stderr_h.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(stderr_h)

    try:
        log_dir = _data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_h = RotatingFileHandler(
            log_dir / "recap-bridge.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_h.setLevel(logging.INFO)
        file_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(file_h)
    except OSError:
        logger.warning("Could not open bridge log file; logging to stderr only.")


def _config_path() -> Path:
    return _data_dir() / "config.yaml"


def _history_path() -> Path:
    return _data_dir() / "history.json"


def _load_settings() -> Settings:
    return Settings.load(_config_path())


def _api_key_configured(provider: str) -> bool:
    """Masked-state lookup that degrades to ``False`` if the keychain is unavailable.

    Reading settings must never hard-fail just because the OS keychain is locked or the
    ``keyring`` backend is missing — that surfaces as 'key not saved' instead. Actual
    key actions (set/delete/test) still raise, since there a clear error is appropriate.
    """
    try:
        return secrets_store.has_api_key(provider)
    except secrets_store.KeychainError:
        logger.warning("Keychain unavailable while reading API-key state for %s.", provider)
        return False


# ── Serialization helpers ──────────────────────────────────────────────────────


def _str_or_none(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _settings_to_dict(settings: Settings) -> dict[str, Any]:
    s = settings.summarization
    sm = s.model
    t = settings.transcription
    tm = t.model
    p = settings.preprocessing
    return {
        "audio": str(settings.audio),
        "transcript": str(settings.transcript),
        "summary": str(settings.summary),
        "output_dir": str(settings.output_dir) if settings.output_dir else None,
        "privacy_ack": settings.privacy_ack,
        "transcription": {
            "language": t.language,
            "model": {
                "provider": tm.provider,
                "name": tm.name,
                "device": tm.device,
                "compute_type": tm.compute_type,
                "beam_size": tm.beam_size,
                "vad_filter": tm.vad_filter,
                "condition_on_previous_text": tm.condition_on_previous_text,
            },
        },
        "summarization": {
            "language": s.language,
            "mode": s.mode,
            "max_transcript_chars": s.max_transcript_chars,
            "timeout_seconds": s.timeout_seconds,
            "retries": s.retries,
            "chunking_mode": s.chunking_mode,
            "model": {
                "provider": sm.provider,
                "name": sm.name,
                # api_key is never returned; expose only whether a key is stored.
                "api_key_configured": _api_key_configured(sm.provider),
                "base_url": sm.base_url,
                "num_ctx": sm.num_ctx,
            },
        },
        "preprocessing": {
            "enabled": p.enabled,
            "sample_rate": p.sample_rate,
            "channels": p.channels,
            "codec": p.codec,
            "loudness_normalization": p.loudness_normalization,
            "target_lufs": p.target_lufs,
            "true_peak_db": p.true_peak_db,
            "loudness_range": p.loudness_range,
            "highpass_hz": p.highpass_hz,
            "keep_temp": p.keep_temp,
        },
        # Per-provider key state (CODE-007): the UI can show "key saved/not saved" for the
        # currently-drafted provider, not only the saved one. Keys are per-provider in the keychain.
        "api_keys_configured": {name: _api_key_configured(name) for name in PROVIDER_PRESETS},
    }


def _event_to_dict(event: workflows.ProgressEvent) -> dict[str, Any]:
    return {
        "step": event.step,
        "status": event.status,
        "message": event.message,
        "percent": event.percent,
        "path": _str_or_none(event.path),
    }


def _result_to_dict(result: workflows.RunResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "transcript_path": _str_or_none(result.transcript_path),
        "summary_path": _str_or_none(result.summary_path),
        "summary_json_path": _str_or_none(result.summary_json_path),
        "transcript_text": result.transcript_text,
        "summary_text": result.summary_text,
        "error_message": result.error_message,
        "output_path": _str_or_none(result.output_path),
    }


# ── Settings commands ──────────────────────────────────────────────────────────

# Keys that may appear in the frontend payload but are not part of the config schema.
_STRIP_SUMMARIZATION_MODEL_KEYS = {"api_key", "api_key_configured"}


def get_settings() -> dict[str, Any]:
    return _settings_to_dict(_load_settings())


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a nested config object and persist it to the desktop config file.

    Secrets are stripped; the payload is round-tripped through ``Settings.load`` so unknown
    keys / invalid values are rejected before anything is written.
    """
    import tempfile  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    data = json.loads(json.dumps(payload))  # deep copy of plain JSON
    data.pop("api_keys_configured", None)  # read-only view field (CODE-007), never persisted
    summarization = data.get("summarization")
    if isinstance(summarization, dict):
        model = summarization.get("model")
        if isinstance(model, dict):
            for key in _STRIP_SUMMARIZATION_MODEL_KEYS:
                model.pop(key, None)

    yaml_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    # Validate by loading from a throwaway file (rejects unknown keys / bad values).
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as f:
        tmp = Path(f.name)
        f.write(yaml_text)
    try:
        Settings.load(tmp)  # ConfigError propagates unchanged to the bridge boundary
    finally:
        tmp.unlink(missing_ok=True)

    write_text_atomic(_config_path(), yaml_text)
    return {"ok": True}


# ── API-key commands ───────────────────────────────────────────────────────────


def set_api_key(provider: str, api_key: str) -> dict[str, Any]:
    if provider not in PROVIDER_PRESETS:
        raise ValueError(f"Неизвестный провайдер: {provider!r}.")
    secrets_store.set_api_key(provider, api_key)
    return {"ok": True}


def delete_api_key(provider: str) -> dict[str, Any]:
    secrets_store.delete_api_key(provider)
    return {"ok": True}


def test_connection(provider: str) -> dict[str, Any]:
    """Lightweight, non-network sanity check for the summarization provider config.

    Verifies that an external provider has a stored API key. A full round-trip to the
    endpoint is intentionally avoided here to keep the UI responsive and offline-safe.
    """
    if provider not in PROVIDER_PRESETS:
        return {"ok": False, "message": f"Неизвестный провайдер: {provider}."}
    settings = _load_settings()
    saved = settings.summarization.model
    # `provider` comes from the (possibly unsaved) UI draft. Only trust the saved base_url when it
    # belongs to the SAME provider; otherwise it describes a different provider and would give a
    # wrong verdict (CODE-005) — fall back to the provider's preset URL.
    base_url = saved.base_url if (saved.base_url and provider == saved.provider) else PROVIDER_PRESETS.get(provider)
    external = workflows.is_external_provider(base_url, provider)
    if external and not secrets_store.has_api_key(provider):
        return {"ok": False, "message": "Для внешнего провайдера не сохранён ключ API."}
    if external:
        return {"ok": True, "message": "Ключ найден. Запрос будет отправлен на внешний сервис."}
    return {"ok": True, "message": f"Локальный провайдер: {base_url}"}


def list_models(provider: str) -> dict[str, Any]:
    """Fetch the available model ids from the provider's OpenAI-compatible ``GET /v1/models``.

    Unlike ``test_connection`` this makes a real (short-timeout) network call. Always returns
    ``{"models": [...], "error": str | None}`` — never raises — so the UI can degrade to its
    manual model input on any failure (offline, missing key, server down).
    """
    if provider not in PROVIDER_PRESETS:
        return {"models": [], "error": f"Неизвестный провайдер: {provider}."}
    settings = _load_settings()
    saved = settings.summarization.model
    # CODE-005: `provider` may be an unsaved UI draft — only trust the saved base_url when it
    # belongs to the SAME provider, else use the preset (avoids querying the wrong endpoint).
    base_url = saved.base_url if (saved.base_url and provider == saved.provider) else PROVIDER_PRESETS.get(provider)
    api_key = secrets_store.get_api_key(provider)
    if workflows.is_external_provider(base_url, provider) and not api_key:
        return {"models": [], "error": "Для внешнего провайдера не сохранён ключ API."}

    import openai  # noqa: PLC0415

    client = openai.OpenAI(api_key=api_key or ("local" if base_url else None), base_url=base_url, timeout=10.0)
    try:
        resp = client.models.list()
    except Exception as exc:  # noqa: BLE001 - boundary: network/HTTP errors → clean UI message
        return {"models": [], "error": workflows.humanize_error(exc)}
    models = sorted({m.id for m in resp.data if getattr(m, "id", None)})
    return {"models": models, "error": None}


# ── History ──────────────────────────────────────────────────────────────────


@contextlib.contextmanager
def _history_lock() -> Iterator[None]:
    """Best-effort exclusive cross-process lock around history read-modify-write.

    Each bridge command is a separate process (spawn-per-call in the Rust host), so a run
    finishing at the same time as a delete/second run could lose a row. A lock on a sidecar
    file serialises the read+write. Cross-platform via ``msvcrt`` (Windows) / ``fcntl`` (POSIX);
    if locking is unavailable it degrades to no lock rather than failing the operation.
    """
    lock_path = _history_path().with_name("history.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        locked = False
        try:
            if sys.platform == "win32":
                import msvcrt  # noqa: PLC0415

                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl  # noqa: PLC0415

                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            locked = True
        except OSError:
            logger.warning("Could not acquire history lock; proceeding without it.")
        try:
            yield
        finally:
            if locked:
                with contextlib.suppress(OSError):
                    if sys.platform == "win32":
                        import msvcrt  # noqa: PLC0415

                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl  # noqa: PLC0415

                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _read_history() -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("History file is unreadable; treating as empty.")
        return []
    items = data.get("items") if isinstance(data, dict) else data
    return items if isinstance(items, list) else []


def _write_history(items: list[dict[str, Any]]) -> None:
    write_text_atomic(_history_path(), json.dumps({"items": items}, ensure_ascii=False, indent=2))


def get_history() -> dict[str, Any]:
    return {"items": _read_history()}


_RESULT_PATH_KEYS = ("transcript_path", "summary_path", "summary_json_path")


def _history_referenced_paths(keys: tuple[str, ...] = _RESULT_PATH_KEYS) -> set[Path]:
    """Resolved result-file paths the history legitimately points at."""
    allowed: set[Path] = set()
    for it in _read_history():
        for key in keys:
            value = it.get(key)
            if value:
                with contextlib.suppress(OSError):
                    allowed.add(Path(value).resolve())
    return allowed


def _is_readable_path(p: Path) -> bool:
    """read_text is scoped (SEC-003) to files the UI legitimately re-opens: history-referenced
    result files, or anything under the app data dir. Everything else is denied so a webview XSS
    cannot turn read_text into an arbitrary-file read."""
    try:
        resolved = p.resolve()
    except OSError:
        return False
    data = _data_dir().resolve()
    if resolved == data or data in resolved.parents:
        return True
    return resolved in _history_referenced_paths()


def _is_writable_summary_path(p: Path) -> bool:
    """Saving an edited summary may only overwrite the summary file of an existing history entry —
    exactly the path the UI hands back after a run or when reopening an entry. Deliberately
    narrower than the read scope: the app data dir stays read-only here, because it holds
    ``config.yaml`` and ``history.json``, which no webview-supplied path may clobber."""
    try:
        resolved = p.resolve()
    except OSError:
        return False
    return resolved in _history_referenced_paths(("summary_path",))


def _safe_base_name(raw: Any) -> str:
    """Validate the export base name: file names are built by concatenating it with a suffix, so it
    must stay a single, plain path component and never steer the write out of the target directory.

    Checked against both path flavours rather than only the host's, plus an explicit ``:`` — on
    Windows that introduces a drive-relative path or an alternate data stream, and ``ntpath`` does
    not treat it as a separator. Characters that are merely illegal in a Windows file name are left
    alone: they are legal on POSIX and a bad one just fails the write.
    """
    name = raw.strip() if isinstance(raw, str) else ""
    if (
        not name
        or name in {".", ".."}
        or ":" in name
        or any(ch < " " or ch == "\x7f" for ch in name)
        or name != PurePosixPath(name).name
        or name != PureWindowsPath(name).name
    ):
        raise ValueError(f"Недопустимое имя файла для экспорта: {raw!r}")
    return name


def read_text(path: str | None) -> dict[str, Any]:
    """Read a result file from disk (used to re-open a history entry). Out-of-scope or missing → empty."""
    if not path:
        return {"text": None, "exists": False}
    p = Path(path)
    # Out-of-scope is reported like "missing" — no path/existence info leaks to the webview.
    if not _is_readable_path(p) or not p.exists():
        return {"text": None, "exists": False}
    try:
        return {"text": p.read_text(encoding="utf-8"), "exists": True}
    except (OSError, UnicodeDecodeError) as exc:
        return {"text": None, "exists": False, "error": str(exc)}


def delete_history_item(item_id: str) -> dict[str, Any]:
    with _history_lock():
        items = [it for it in _read_history() if it.get("id") != item_id]
        _write_history(items)
    return {"ok": True}


def _append_history(entry: dict[str, Any]) -> None:
    with _history_lock():
        items = _read_history()
        items.insert(0, entry)  # newest first
        _write_history(items)


# ── Export ─────────────────────────────────────────────────────────────────────


def export_summary(payload: dict[str, Any]) -> dict[str, Any]:
    from formatters import parse_summary_text, render_markdown, to_html, to_json, to_plain  # noqa: PLC0415
    from summary_schema import SummaryValidationError, load_summary_json  # noqa: PLC0415

    formats = payload.get("formats") or ["markdown", "plain", "html", "json"]
    target_dir = Path(payload["target_dir"])
    # Both inputs come from the webview, and both are constrained so the four writes below stay
    # inside the chosen directory: the base name must be a plain file-name component, and the
    # directory itself must already exist (SEC-003 — no arbitrary directory trees are created).
    base_name = _safe_base_name(payload["base_name"])
    mode = payload.get("mode") or "medium"

    if not target_dir.is_dir():
        raise ValueError(f"Каталог для экспорта не существует: {target_dir}")

    # The base .json (written by the run and by "Сохранить") is the single source of truth: every
    # exported format is rendered from it. Fall back to parsing the (edited) summary_text when there
    # is no JSON, when the JSON is an old pre-structured {mode, summary} file that deserializes to an
    # empty object, or when the file on disk is corrupt (truncated, hand-edited, not UTF-8) —
    # otherwise a reopened old-format item would export blank and a damaged file would block the
    # export outright, even though the payload carries a perfectly good summary text.
    json_path = payload.get("summary_json_path")
    summary = None
    if json_path and Path(json_path).is_file():
        try:
            summary = load_summary_json(Path(json_path).read_text(encoding="utf-8"))
        except (SummaryValidationError, UnicodeDecodeError):
            logger.warning("Base summary JSON is unusable; exporting from the text: %s", json_path, exc_info=True)
            summary = None
        if summary is not None and not summary.blocks:  # old/foreign JSON with no blocks
            summary = None
    if summary is None:
        summary = parse_summary_text(payload.get("summary_text") or "", mode)
    if not summary.blocks:
        # Nothing survived either source — writing four empty files would look like a successful export.
        raise ValueError("Нечего экспортировать: текст саммари пуст, а файл .json отсутствует или повреждён")
    out: dict[str, Any] = {"markdown_path": None, "plain_path": None, "html_path": None, "json_path": None}

    if "markdown" in formats:
        path = target_dir / f"{base_name}_summary.md"
        write_text_atomic(path, render_markdown(summary))
        out["markdown_path"] = str(path)
    if "plain" in formats:
        # Distinct name: {base}_summary.txt is the summary the run wrote and history reopens —
        # exporting must not overwrite it (the export may target that same folder, and the base file
        # holds the user's edits, while this one is re-rendered from the saved .json).
        path = target_dir / f"{base_name}_summary_plain.txt"
        write_text_atomic(path, to_plain(summary))
        out["plain_path"] = str(path)
    if "html" in formats:
        path = target_dir / f"{base_name}_summary.html"
        write_text_atomic(path, to_html(summary))
        out["html_path"] = str(path)
    if "json" in formats:
        path = target_dir / f"{base_name}_summary.json"
        write_text_atomic(path, to_json(summary))
        out["json_path"] = str(path)

    return out


def check_model() -> dict[str, Any]:
    """Report whether the configured summarization model is available (Ollama pull check).

    Only Ollama can pull models; for other providers (and when Ollama is unreachable) this returns
    ``installed: True`` so the run proceeds and surfaces any real error itself.
    """
    from config import PROVIDER_PRESETS  # noqa: PLC0415

    settings = _load_settings()
    model_cfg = settings.summarization.model
    provider = model_cfg.provider
    model = model_cfg.name
    base_url = model_cfg.base_url or PROVIDER_PRESETS.get(provider)
    out: dict[str, Any] = {"installed": True, "provider": provider, "model": model, "base_url": base_url}
    if provider != "ollama" or not base_url:
        return out
    import ollama_support  # noqa: PLC0415

    try:
        out["installed"] = ollama_support.model_installed(base_url, model)
    except Exception:  # noqa: BLE001 - Ollama unreachable → don't block; the run surfaces it
        logger.warning("Ollama model check failed", exc_info=True)
    return out


def pull_model(payload: dict[str, Any], *, emit: Any, cancel: Any) -> workflows.RunResult:
    """Streaming: pull the Ollama model, reporting progress as a ``download`` step."""
    import ollama_support  # noqa: PLC0415

    base_url = payload["base_url"]
    model = payload["model"]

    def on_progress(completed: int, total: int, status: str) -> None:
        pct = (completed / total) if total else None
        emit(workflows.ProgressEvent(workflows.STEP_DOWNLOAD, "running", status or "Загрузка модели…", percent=pct))

    emit(workflows.ProgressEvent(workflows.STEP_DOWNLOAD, "running", f"Загрузка модели {model}…", percent=None))
    try:
        ollama_support.pull_model(base_url, model, on_progress, cancel)
    except ollama_support.PullCancelled:
        emit(workflows.ProgressEvent(workflows.STEP_DOWNLOAD, "cancelled", "Загрузка модели отменена."))
        return workflows.RunResult("cancelled", None, None, None, None, None, "Загрузка модели отменена.")
    except Exception as exc:  # noqa: BLE001 - boundary
        logger.exception("Model pull failed")
        msg = f"Не удалось загрузить модель: {workflows.humanize_error(exc)}"
        emit(workflows.ProgressEvent(workflows.STEP_DOWNLOAD, "error", msg))
        return workflows.RunResult("failed", None, None, None, None, None, msg)
    emit(workflows.ProgressEvent(workflows.STEP_DOWNLOAD, "success", "Модель загружена."))
    return workflows.RunResult("success", None, None, None, None, None, None)


def save_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist the edited summary: overwrite the canonical ``.txt`` and re-derive the structured
    ``.json`` from it (parse → object → JSON). Mirrors what a run writes, so reopening the history
    item reflects the edits. The text is the plain-text form; ``parse_summary_text`` still accepts
    the Markdown written by pre-plain-text runs.

    The target is restricted to a summary file the history points at, so this command cannot be
    turned into a write to an arbitrary location on disk."""
    from formatters import parse_summary_text, to_json  # noqa: PLC0415

    summary_text = payload["summary_text"]
    summary_path = Path(payload["summary_path"])
    mode = payload.get("mode") or "medium"

    if not _is_writable_summary_path(summary_path):
        raise ValueError(f"Файл саммари не найден в истории запусков: {summary_path}")
    if not summary_path.parent.is_dir():
        raise ValueError(f"Каталог не существует: {summary_path.parent}")

    json_path = summary_path.with_name(f"{summary_path.stem}.json")
    write_text_atomic(summary_path, summary_text)
    write_text_atomic(json_path, to_json(parse_summary_text(summary_text, mode)))
    return {"summary_path": str(summary_path), "json_path": str(json_path)}


# ── run_recap ────────────────────────────────────────────────────────────────


def _build_run_options(payload: dict[str, Any]) -> RunOptions:
    overrides = payload.get("overrides") or {}
    audio_path = payload.get("audio_path")  # absent for standalone summarize (input is a transcript)
    transcript_path = payload.get("transcript_path")
    summary_path = payload.get("summary_path")
    return RunOptions(
        audio_path=Path(audio_path) if audio_path else None,
        transcript_path=Path(transcript_path) if transcript_path else None,
        summary_path=Path(summary_path) if summary_path else None,
        transcription_language=overrides.get("transcription_language"),
        summary_language=overrides.get("summary_language"),
        provider=overrides.get("provider"),
        model=overrides.get("model"),
        mode=overrides.get("mode"),
    )


def _settings_with_api_key(settings: Settings, provider: str) -> Settings:
    """Inject the keychain-stored API key for ``provider`` into a frozen Settings copy.

    A keychain failure here must not abort the run (local providers need no key); the run
    proceeds without a key and any external provider surfaces a clear auth error later.
    """
    try:
        key = secrets_store.get_api_key(provider)
    except secrets_store.KeychainError:
        logger.warning("Keychain unavailable while reading API key for %s; running without it.", provider)
        key = None
    if not key:
        return settings
    model = dataclasses.replace(settings.summarization.model, api_key=key)
    summarization = dataclasses.replace(settings.summarization, model=model)
    return dataclasses.replace(settings, summarization=summarization)


def _maybe_emit_privacy_warning(
    settings: Settings, provider: str, emit: workflows.ProgressCallback | None
) -> None:
    """Warn (once, via ``emit``) if the transcript will leave the machine for an external provider."""
    if emit is None or settings.privacy_ack:
        return
    base_url = settings.summarization.model.base_url or PROVIDER_PRESETS.get(provider)
    if workflows.is_external_provider(base_url, provider):
        emit(
            workflows.ProgressEvent(
                workflows.STEP_SUMMARIZE,
                "warning",
                "Транскрипт будет отправлен во внешний сервис. Подтвердите это в настройках приватности.",
            )
        )


def run_recap(
    payload: dict[str, Any],
    *,
    emit: workflows.ProgressCallback | None = None,
    cancel: workflows.CancelCheck | None = None,
    transcriber_factory: workflows.TranscriberFactory | None = None,
) -> workflows.RunResult:
    """Run one file and record a history entry. Returns the structured result.

    ``emit`` receives every progress event; the history entry stores only paths/metadata
    (never the transcript or summary text). ``transcriber_factory`` lets the persistent worker
    (``serve``) reuse a warm Whisper model across runs (PERF-001); when None a fresh model is built.
    """
    options = _build_run_options(payload)
    settings = _load_settings()
    provider = options.provider or settings.summarization.model.provider
    settings = _settings_with_api_key(settings, provider)

    # run_mode selects the pipeline slice (default "full"). "summarize" is a separate command
    # (resummarize). NOTE: distinct from options.mode, which is the *summary* mode (brief/medium/…).
    run_mode = payload.get("run_mode", "full")

    if run_mode == "preprocess":
        result = workflows.preprocess_one(options, settings=settings, progress=emit)
    elif run_mode == "transcribe":
        # Transcription never preprocesses in the desktop (the enable toggle was removed) — force
        # preprocessing off regardless of the config value.
        transcribe_settings = dataclasses.replace(
            settings, preprocessing=dataclasses.replace(settings.preprocessing, enabled=False)
        )
        result = workflows.run_one_file(
            options,
            settings=transcribe_settings,
            progress=emit,
            cancel=cancel,
            transcriber_factory=transcriber_factory,
            stop_after="transcribe",
        )
    else:  # full — summarization sends the transcript out, so warn; preprocessing is mandatory.
        _maybe_emit_privacy_warning(settings, provider, emit)
        result = workflows.run_one_file(
            options,
            settings=settings,
            progress=emit,
            cancel=cancel,
            transcriber_factory=transcriber_factory,
            force_preprocess=True,
            summary_format=DESKTOP_SUMMARY_FORMAT,
        )

    _record_history(options, provider, settings, result, run_mode=run_mode)
    return result


def resummarize(
    payload: dict[str, Any],
    *,
    emit: workflows.ProgressCallback | None = None,
    cancel: workflows.CancelCheck | None = None,
) -> workflows.RunResult:
    """Re-run only summarization on an existing transcript and record a history entry.

    Used by "Повторить суммаризацию": no re-transcription, so long meetings are cheap to retry.
    ``cancel`` is polled around the LLM call, so a stop lands in history as ``cancelled``.
    """
    options = _build_run_options(payload)
    settings = _load_settings()
    provider = options.provider or settings.summarization.model.provider
    settings = _settings_with_api_key(settings, provider)

    _maybe_emit_privacy_warning(settings, provider, emit)

    result = workflows.resummarize_one(
        options, settings=settings, progress=emit, cancel=cancel, summary_format=DESKTOP_SUMMARY_FORMAT
    )
    _record_history(options, provider, settings, result, run_mode="summarize")
    return result


def _record_history(
    options: RunOptions, provider: str, settings: Settings, result: workflows.RunResult, run_mode: str = "full"
) -> None:
    """Append a history entry (paths + metadata only — never transcript/summary text)."""
    entry = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().astimezone().isoformat(),
        "run_mode": run_mode,
        "audio_path": str(options.audio_path) if options.audio_path else "",
        "audio_name": options.audio_path.name if options.audio_path else "",
        "status": result.status,
        "output_path": _str_or_none(result.output_path),
        "transcript_path": _str_or_none(result.transcript_path),
        "summary_path": _str_or_none(result.summary_path),
        "summary_json_path": _str_or_none(result.summary_json_path),
        "provider": provider,
        "model": options.model or settings.summarization.model.name,
        "mode": options.mode or settings.summarization.mode,
        "transcription_language": options.transcription_language or settings.transcription.language,
        "summary_language": options.summary_language or settings.summarization.language,
        "duration_seconds": None,
        "error_message": result.error_message,
    }
    _append_history(entry)


# ── Subprocess entrypoint (recap-bridge) ───────────────────────────────────────


def _emit_line(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


_STREAMING_COMMANDS = {
    "run_recap": run_recap,
    "resummarize": resummarize,
    "pull_model": pull_model,
}


def _streaming(command: str, payload: dict[str, Any]) -> int:
    def emit(event: workflows.ProgressEvent) -> None:
        _emit_line({"type": "progress", "event": _event_to_dict(event)})

    # Cooperative cancellation (ARCH-002): the Rust host passes the path of a flag file it
    # creates when the user hits "Stop". The workflow polls this between stages and returns a
    # real RunResult("cancelled") — so the transcript pointer and history entry are preserved.
    # Popped here so it never reaches _build_run_options.
    cancel_flag = payload.pop("cancel_flag", None)
    cancel: workflows.CancelCheck | None = Path(cancel_flag).exists if cancel_flag else None

    runner = _STREAMING_COMMANDS[command]
    try:
        result = runner(payload, emit=emit, cancel=cancel)
    except Exception as exc:  # noqa: BLE001 - boundary: report, never crash silently
        logger.exception("%s failed", command)
        _emit_line({"type": "error", "error": workflows.humanize_error(exc)})
        return 1
    _emit_line({"type": "result", "result": _result_to_dict(result)})
    return 0


def _transcriber_key(settings: Settings) -> tuple[Any, ...]:
    """Cache key for the transcriber — only the fields that change the loaded model."""
    m = settings.transcription.model
    return (m.provider, m.name, m.device, m.compute_type, m.beam_size, m.vad_filter, m.condition_on_previous_text)


def serve(lines: Iterable[str] | None = None) -> int:
    """Persistent worker (PERF-001): keep the Whisper model warm across ``run_recap`` requests.

    Reads one JSON run-request per line from stdin and streams, per run, the same framing as
    ``_streaming``: ``{"type":"progress"}`` events then a terminal ``{"type":"result"}`` /
    ``{"type":"error"}`` line (the Rust host reads until that terminal line and keeps the pipe
    open). Only ``run_recap`` is served here — ``resummarize`` is LLM-only and stays spawn-per-call.

    At most one transcriber is cached; a change to the transcription model drops the old one
    (freeing GPU memory) before building the new.
    """
    _force_utf8_io()
    _configure_logging()
    cache: dict[tuple[Any, ...], WhisperTranscriber] = {}

    def factory(settings: Settings) -> WhisperTranscriber:
        key = _transcriber_key(settings)
        if key not in cache:
            cache.clear()  # release the previous model before building a new one
            from providers.factory import make_transcriber  # noqa: PLC0415

            cache[key] = make_transcriber(settings)
        return cache[key]

    def emit(event: workflows.ProgressEvent) -> None:
        _emit_line({"type": "progress", "event": _event_to_dict(event)})

    for raw in lines if lines is not None else sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            _emit_line({"type": "error", "error": f"Некорректный JSON: {exc}"})
            continue
        cancel_flag = payload.pop("cancel_flag", None)
        cancel: workflows.CancelCheck | None = Path(cancel_flag).exists if cancel_flag else None
        try:
            result = run_recap(payload, emit=emit, cancel=cancel, transcriber_factory=factory)
        except Exception as exc:  # noqa: BLE001 - boundary: report, never crash the worker
            logger.exception("serve run failed")
            _emit_line({"type": "error", "error": workflows.humanize_error(exc)})
            continue
        _emit_line({"type": "result", "result": _result_to_dict(result)})
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_io()
    _configure_logging()
    args = sys.argv[1:] if argv is None else argv
    if not args:
        _emit_line({"error": "Команда не указана."})
        return 1

    command = args[0]
    if command == "serve":  # persistent worker: reads many requests, not a single payload
        return serve()

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        _emit_line({"error": f"Некорректный JSON во вводе: {exc}"})
        return 1

    if command in _STREAMING_COMMANDS:
        return _streaming(command, payload)

    try:
        if command == "get_settings":
            out = get_settings()
        elif command == "save_settings":
            out = save_settings(payload)
        elif command == "set_api_key":
            out = set_api_key(payload["provider"], payload["api_key"])
        elif command == "delete_api_key":
            out = delete_api_key(payload["provider"])
        elif command == "test_connection":
            out = test_connection(payload["provider"])
        elif command == "list_models":
            out = list_models(payload["provider"])
        elif command == "export_summary":
            out = export_summary(payload)
        elif command == "save_summary":
            out = save_summary(payload)
        elif command == "check_model":
            out = check_model()
        elif command == "get_history":
            out = get_history()
        elif command == "read_text":
            out = read_text(payload.get("path"))
        elif command == "delete_history_item":
            out = delete_history_item(payload["id"])
        else:
            _emit_line({"error": f"Неизвестная команда: {command}"})
            return 1
    except Exception as exc:  # noqa: BLE001 - boundary: translate to JSON error envelope
        logger.exception("bridge command %s failed", command)
        _emit_line({"error": workflows.humanize_error(exc)})
        return 1

    _emit_line(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
