"""Reusable transcription/summarization workflows shared by the CLI and the desktop bridge.

The CLI (`cli.py`) keeps owning its own user-facing messages and error boundary; this
module holds the provider-agnostic pipeline so the desktop bridge can drive the exact
same logic without parsing CLI stdout.

Design rules honoured here (see CLAUDE.md / AGENTS.md):
- provider wiring only through ``providers.factory`` (imported lazily so importing this
  module never triggers a CUDA/faster-whisper load);
- transcript is written to disk *before* the LLM is called, so an LLM failure still
  leaves the transcript on disk and yields ``partial_success``;
- all file writes go through ``utils.write_text_atomic``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from config import Settings

if TYPE_CHECKING:
    from models import MeetingSummary
    from providers.llm import LLMSummarizer
    from providers.whisper import WhisperTranscriber
    from transcript import Transcript

# Builds (or returns a cached) transcriber for the given settings. The desktop worker passes a
# caching factory here so the Whisper model stays warm across runs (PERF-001); everyone else
# gets the default make_transcriber (a fresh model per call).
TranscriberFactory = Callable[[Settings], "WhisperTranscriber"]

logger = logging.getLogger(__name__)

_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
# Single source of truth for accepted audio/video containers (imported by cli.py and mirrored
# in desktop/src/lib/bridge.ts). ffmpeg/faster-whisper handle all of these.
AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".mkv", ".webm", ".flac"})

# ── Steps / statuses (kept in sync with docs/desktop-bridge-contract.md) ─────────
STEP_PREPROCESS = "preprocess"
STEP_TRANSCRIBE = "transcribe"
STEP_SUMMARIZE = "summarize"
STEP_EXPORT = "export"


@dataclass(frozen=True)
class RunOptions:
    """One-file run request. ``None`` fields fall back to loaded ``Settings``.

    ``audio_path`` may be ``None`` for summarize-only flows (``resummarize_one``), which read an
    existing transcript and never touch the audio.
    """

    audio_path: Path | None = None
    transcript_path: Path | None = None
    summary_path: Path | None = None
    transcription_language: str | None = None
    summary_language: str | None = None
    provider: str | None = None
    model: str | None = None
    mode: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    step: str  # preprocess | transcribe | summarize | export
    status: str  # pending | running | success | warning | error | cancelled
    message: str
    percent: float | None = None
    path: Path | None = None


@dataclass(frozen=True)
class RunResult:
    status: str  # success | partial_success | failed | cancelled
    transcript_path: Path | None
    summary_path: Path | None
    summary_json_path: Path | None
    transcript_text: str | None
    summary_text: str | None
    error_message: str | None = None
    # Only set by preprocess-only runs: the produced *.preprocessed.wav (no transcript/summary).
    output_path: Path | None = None


ProgressCallback = Callable[[ProgressEvent], None]
CancelCheck = Callable[[], bool]


def _noop(_event: ProgressEvent) -> None:  # pragma: no cover - trivial default
    return None


def _never_cancelled() -> bool:  # pragma: no cover - trivial default
    return False


def is_external_provider(base_url: str | None, provider: str) -> bool:
    """True when summarization would send the transcript to a non-local endpoint."""
    if provider == "openai" and base_url is None:
        return True
    if base_url is None:
        return False
    hostname = urlparse(base_url).hostname or ""
    return hostname not in _LOCAL_HOSTNAMES


def humanize_error(exc: BaseException) -> str:
    """Map an exception to a short, user-facing Russian message (no stack trace)."""
    name = type(exc).__name__
    detail = str(exc).strip()
    if name in ("APITimeoutError", "Timeout", "TimeoutError"):
        return "Превышено время ожидания ответа модели."
    if name in ("APIConnectionError", "ConnectionError"):
        return "Не удалось подключиться к LLM-провайдеру. Проверьте адрес и доступность сервиса."
    if name == "AuthenticationError" or "api key" in detail.lower() or "api_key" in detail.lower():
        return "Ошибка авторизации LLM: проверьте сохранённый ключ API."
    if name == "ConfigError":
        return f"Ошибка конфигурации: {detail}"
    if not detail:
        return f"Произошла ошибка ({name})."
    return detail


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _json_sibling(summary_path: Path) -> Path:
    return summary_path.with_name(f"{summary_path.stem}.json")


def run_one_file(
    options: RunOptions,
    *,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
    cancel: CancelCheck | None = None,
    transcriber_factory: TranscriberFactory | None = None,
    stop_after: str | None = None,
    force_preprocess: bool = False,
) -> RunResult:
    """Run the full one-file pipeline and return a structured result.

    ``stop_after="transcribe"`` runs preprocess + transcribe only (transcribe-only mode): the
    transcript is written and the run returns ``success`` before summarization — an empty
    transcript is success-with-warning here (transcription ran, just found no speech).
    ``force_preprocess=True`` runs preprocessing even if ``settings.preprocessing.enabled`` is
    False (used by full mode, where preprocessing is a mandatory step).

    Unlike the low-level helpers, this orchestrator catches errors at step boundaries
    and turns them into a ``RunResult`` with a user-facing ``error_message`` (technical
    detail goes to the logger). It always writes the transcript before the LLM call, so
    an LLM failure yields ``partial_success`` with the transcript still on disk.

    It writes a Telegram-formatted ``.txt`` summary and a ``.json`` summary; the plain
    text format is only produced by ``export_summary`` in the bridge.
    """
    from preprocessing import PreprocessingError, prepared_audio  # noqa: PLC0415
    from providers.factory import make_summarizer, make_transcriber  # noqa: PLC0415
    from utils import write_text_atomic  # noqa: PLC0415

    emit = progress if progress is not None else _noop
    cancelled = cancel if cancel is not None else _never_cancelled

    if settings is None:
        settings = Settings.load()

    provider_name = options.provider or settings.summarization.model.provider
    mode_name = options.mode or settings.summarization.mode
    transcript_path = options.transcript_path or settings.transcript
    summary_path = options.summary_path or settings.summary
    summary_json_path = _json_sibling(summary_path)
    audio_path = options.audio_path

    def failed(step: str, message: str) -> RunResult:
        emit(ProgressEvent(step, "error", message))
        return RunResult("failed", None, None, None, None, None, message)

    # ── Input validation ────────────────────────────────────────────────────────
    if audio_path is None or not audio_path.exists():
        return failed(STEP_PREPROCESS, f"Аудиофайл не найден: {audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(ext.lstrip(".").upper() for ext in AUDIO_EXTENSIONS))
        return failed(STEP_PREPROCESS, f"Неподдерживаемый формат аудио: {audio_path.suffix}. Поддерживаются: {supported}.")

    # Build the summarizer once, up front (validates provider/mode/language: raises ValueError).
    # The same instance is reused in _summarize_and_export — no second construction. Transcribe-only
    # never summarizes, so it must NOT require a summarization key/provider to be configured.
    summarizer: LLMSummarizer | None = None
    if stop_after != STEP_TRANSCRIBE:
        try:
            summarizer = make_summarizer(settings, provider_name, mode_name, options.model, options.summary_language)
        except ValueError as exc:
            return failed(STEP_SUMMARIZE, str(exc))

    try:
        _ensure_parent(transcript_path)
        _ensure_parent(summary_path)
    except OSError as exc:
        return failed(STEP_EXPORT, f"Каталог для результатов недоступен: {exc}")

    if cancelled():
        return RunResult("cancelled", None, None, None, None, None, "Остановлено пользователем.")

    # ── Transcribe (preprocess inside) ────────────────────────────────────────────
    build_transcriber = transcriber_factory or make_transcriber
    try:
        transcriber = build_transcriber(settings)
    except Exception as exc:
        logger.exception("Failed to load transcription model")
        return failed(STEP_TRANSCRIBE, f"Не удалось загрузить модель распознавания: {humanize_error(exc)}")

    lang = options.transcription_language or settings.transcription.language
    # Full mode makes preprocessing mandatory (force_preprocess), overriding a disabled setting.
    prep_cfg = replace(settings.preprocessing, enabled=True) if force_preprocess else settings.preprocessing
    try:
        if prep_cfg.enabled:
            emit(ProgressEvent(STEP_PREPROCESS, "running", "Предобработка аудио…"))
        with prepared_audio(audio_path, prep_cfg) as prepared:
            if prep_cfg.enabled:
                emit(ProgressEvent(STEP_PREPROCESS, "success", "Аудио подготовлено."))
            # percent=None → indeterminate spinner until the first segment reports real progress
            # (avoids the ring sitting at a literal "0%" while the model warms up / first chunk runs).
            emit(ProgressEvent(STEP_TRANSCRIBE, "running", "Транскрибация началась.", percent=None))

            def on_segment(pct: float) -> None:  # CODE-006: real per-segment progress
                emit(ProgressEvent(STEP_TRANSCRIBE, "running", f"Транскрибация… {int(pct * 100)}%", percent=pct))

            transcript = transcriber.transcribe(prepared, lang, on_progress=on_segment)
    except PreprocessingError as exc:
        logger.exception("Preprocessing failed")
        return failed(STEP_PREPROCESS, f"Ошибка предобработки аудио: {humanize_error(exc)}")
    except Exception as exc:
        logger.exception("Transcription failed")
        return failed(STEP_TRANSCRIBE, f"Ошибка транскрибации: {humanize_error(exc)}")

    # ── Persist transcript BEFORE the LLM call ─────────────────────────────────────
    transcript_text = transcript.to_file_format()
    try:
        write_text_atomic(transcript_path, transcript_text)
    except OSError as exc:
        return failed(STEP_TRANSCRIBE, f"Не удалось сохранить транскрипт: {exc}")
    emit(ProgressEvent(STEP_TRANSCRIBE, "success", f"Транскрипт сохранён: {transcript_path}", path=transcript_path))

    # Transcribe-only: stop here with the transcript on disk. Empty is success-with-warning
    # (transcription ran and produced a file; it just found no speech) — not a failure.
    if stop_after == STEP_TRANSCRIBE:
        if transcript.is_empty:
            emit(ProgressEvent(STEP_TRANSCRIBE, "warning", "Речь не распознана — транскрипт пуст."))
        return RunResult("success", transcript_path, None, None, transcript_text, None, None)

    if transcript.is_empty:
        msg = "Речь не распознана — саммари не создано."
        emit(ProgressEvent(STEP_TRANSCRIBE, "warning", msg))
        return RunResult("failed", transcript_path, None, None, transcript_text, None, msg)

    if cancelled():
        msg = "Остановлено пользователем после транскрибации."
        emit(ProgressEvent(STEP_SUMMARIZE, "cancelled", msg))
        return RunResult("cancelled", transcript_path, None, None, transcript_text, None, msg)

    # ── Summarize + export (shared with resummarize_one) ────────────────────────────
    assert summarizer is not None  # built above whenever stop_after != "transcribe"
    return _summarize_and_export(
        settings,
        transcript,
        summarizer=summarizer,
        options=options,
        provider_name=provider_name,
        mode_name=mode_name,
        transcript_path=transcript_path,
        summary_path=summary_path,
        summary_json_path=summary_json_path,
        transcript_text=transcript_text,
        emit=emit,
    )


def preprocess_one(
    options: RunOptions,
    *,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
) -> RunResult:
    """Preprocess-only mode: run ffmpeg and write a persistent ``<stem>.preprocessed.wav``.

    Like the CLI ``preprocess`` command, invoking this IS the request, so it always runs ffmpeg
    (ignores ``preprocessing.enabled``). The output goes into ``settings.output_dir`` (or next to
    the audio when unset); the path is returned on ``RunResult.output_path`` and on the success
    event so the desktop can reveal it.
    """
    from preprocessing import PreprocessingError, preprocess_audio  # noqa: PLC0415

    emit = progress if progress is not None else _noop
    if settings is None:
        settings = Settings.load()
    audio_path = options.audio_path

    def failed(message: str) -> RunResult:
        emit(ProgressEvent(STEP_PREPROCESS, "error", message))
        return RunResult("failed", None, None, None, None, None, message)

    if audio_path is None or not audio_path.exists():
        return failed(f"Аудиофайл не найден: {audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(ext.lstrip(".").upper() for ext in AUDIO_EXTENSIONS))
        return failed(f"Неподдерживаемый формат аудио: {audio_path.suffix}. Поддерживаются: {supported}.")

    out_dir = settings.output_dir or audio_path.parent
    output_path = out_dir / f"{audio_path.stem}.preprocessed.wav"
    try:
        _ensure_parent(output_path)
    except OSError as exc:
        return failed(f"Каталог для результатов недоступен: {exc}")

    emit(ProgressEvent(STEP_PREPROCESS, "running", "Предобработка аудио…"))
    try:
        preprocess_audio(audio_path, output_path, settings.preprocessing)
    except PreprocessingError as exc:
        logger.exception("Preprocessing failed")
        return failed(f"Ошибка предобработки аудио: {humanize_error(exc)}")
    except Exception as exc:
        logger.exception("Preprocessing failed")
        return failed(f"Ошибка предобработки аудио: {humanize_error(exc)}")

    emit(ProgressEvent(STEP_PREPROCESS, "success", f"Готово: {output_path}", path=output_path))
    return RunResult("success", None, None, None, None, None, None, output_path=output_path)


def _generate_summary(summarizer: LLMSummarizer, transcript_text: str, mode_name: str) -> MeetingSummary:
    """Produce a structured summary: try JSON generation, else fall back to the text path.

    Structured (JSON) generation is attempted only when the summarizer supports it (a JSON prompt
    is registered for this mode). Any failure — provider rejects ``response_format``, invalid JSON,
    schema mismatch — falls back to the text prompt + Markdown parsing so local models never break.
    A failure of the *fallback* call propagates to the caller's step boundary.
    """
    from formatters import parse_summary  # noqa: PLC0415
    from summary_schema import SummaryValidationError, parse_summary_json  # noqa: PLC0415

    if summarizer.supports_structured:
        try:
            raw_json = summarizer.summarize(transcript_text, structured=True)
            return parse_summary_json(raw_json, mode_name)
        except SummaryValidationError as exc:
            logger.warning("Structured summary did not validate (%s); falling back to text path.", exc)
        except Exception:  # noqa: BLE001 - any provider/generation error → text fallback
            logger.warning("Structured summary generation failed; falling back to text path.", exc_info=True)

    raw = summarizer.summarize(transcript_text)
    return parse_summary(raw, mode_name)


def _summarize_and_export(
    settings: Settings,
    transcript: Transcript,
    *,
    summarizer: LLMSummarizer,
    options: RunOptions,
    provider_name: str,
    mode_name: str,
    transcript_path: Path,
    summary_path: Path,
    summary_json_path: Path,
    transcript_text: str,
    emit: ProgressCallback,
) -> RunResult:
    """Summarize an in-memory transcript and write the .txt/.json summaries.

    Shared by ``run_one_file`` and ``resummarize_one``, which build the ``summarizer`` once
    (during early validation) and hand it in. On LLM/IO failure returns ``partial_success``
    with the transcript paths preserved.
    """
    from formatters import render_markdown, to_json  # noqa: PLC0415
    from utils import write_text_atomic  # noqa: PLC0415

    model_label = options.model or settings.summarization.model.name
    emit(ProgressEvent(STEP_SUMMARIZE, "running", f"Суммаризация началась: {provider_name} / {model_label}."))
    try:
        summary = _generate_summary(summarizer, transcript.to_text(), mode_name)
    except Exception as exc:
        logger.exception("Summarization failed")
        msg = humanize_error(exc)
        emit(ProgressEvent(STEP_SUMMARIZE, "error", msg))
        # partial_success: transcript is on disk, only summarization failed.
        return RunResult("partial_success", transcript_path, None, None, transcript_text, None, msg)
    emit(ProgressEvent(STEP_SUMMARIZE, "success", "Саммари готово."))

    emit(ProgressEvent(STEP_EXPORT, "running", "Сохранение результатов…"))
    markdown_text = render_markdown(summary)
    try:
        write_text_atomic(summary_path, markdown_text)
        write_text_atomic(summary_json_path, to_json(summary))
    except OSError as exc:
        msg = f"Не удалось сохранить саммари: {exc}"
        emit(ProgressEvent(STEP_EXPORT, "error", msg))
        return RunResult("partial_success", transcript_path, None, None, transcript_text, markdown_text, msg)
    emit(ProgressEvent(STEP_EXPORT, "success", f"Готово: {summary_path}", path=summary_path))

    return RunResult(
        status="success",
        transcript_path=transcript_path,
        summary_path=summary_path,
        summary_json_path=summary_json_path,
        transcript_text=transcript_text,
        summary_text=markdown_text,
        error_message=None,
    )


def resummarize_one(
    options: RunOptions,
    *,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
) -> RunResult:
    """Re-run summarization only, reusing the transcript already on disk.

    Used by the desktop "Повторить суммаризацию" action after a ``partial_success`` (or
    to regenerate with different settings) — it never re-transcribes, so long meetings
    are not re-processed. Requires ``options.transcript_path`` to point at a saved
    transcript.
    """
    from providers.factory import make_summarizer  # noqa: PLC0415
    from transcript import Transcript  # noqa: PLC0415

    emit = progress if progress is not None else _noop
    if settings is None:
        settings = Settings.load()

    provider_name = options.provider or settings.summarization.model.provider
    mode_name = options.mode or settings.summarization.mode
    transcript_path = options.transcript_path or settings.transcript
    summary_path = options.summary_path or settings.summary
    summary_json_path = _json_sibling(summary_path)

    if not transcript_path.exists():
        msg = f"Транскрипт не найден: {transcript_path}"
        emit(ProgressEvent(STEP_SUMMARIZE, "error", msg))
        return RunResult("failed", None, None, None, None, None, msg)

    try:
        summarizer = make_summarizer(settings, provider_name, mode_name, options.model, options.summary_language)
    except ValueError as exc:
        emit(ProgressEvent(STEP_SUMMARIZE, "error", str(exc)))
        return RunResult("failed", transcript_path, None, None, None, None, str(exc))

    try:
        transcript = Transcript.from_file(transcript_path)
    except (OSError, UnicodeDecodeError) as exc:
        msg = f"Не удалось прочитать транскрипт: {exc}"
        emit(ProgressEvent(STEP_SUMMARIZE, "error", msg))
        return RunResult("failed", transcript_path, None, None, None, None, msg)

    transcript_text = transcript.to_file_format()
    if transcript.is_empty:
        msg = "Транскрипт пуст — саммари не создано."
        emit(ProgressEvent(STEP_SUMMARIZE, "warning", msg))
        return RunResult("failed", transcript_path, None, None, transcript_text, None, msg)

    try:
        _ensure_parent(summary_path)
    except OSError as exc:
        msg = f"Каталог для результатов недоступен: {exc}"
        emit(ProgressEvent(STEP_EXPORT, "error", msg))
        return RunResult("partial_success", transcript_path, None, None, transcript_text, None, msg)

    emit(ProgressEvent(STEP_TRANSCRIBE, "success", "Используется сохранённый транскрипт.", path=transcript_path))
    return _summarize_and_export(
        settings,
        transcript,
        summarizer=summarizer,
        options=options,
        provider_name=provider_name,
        mode_name=mode_name,
        transcript_path=transcript_path,
        summary_path=summary_path,
        summary_json_path=summary_json_path,
        transcript_text=transcript_text,
        emit=emit,
    )
