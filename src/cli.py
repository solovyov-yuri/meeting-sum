from __future__ import annotations

import logging
import sys
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated

import typer

if isinstance(sys.stdout, TextIOWrapper):
    sys.stdout.reconfigure(write_through=True)

app = typer.Typer(help="Meeting transcription and summarization tool")
logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
    )


def _is_external(base_url: str | None, provider: str) -> bool:
    from workflows import is_external_provider  # noqa: PLC0415

    return is_external_provider(base_url, provider)


def _warn_if_external(base_url: str | None, provider: str, privacy_ack: bool) -> None:
    if privacy_ack or not _is_external(base_url, provider):
        return
    endpoint = base_url or "https://api.openai.com"
    typer.echo(
        f"Warning: transcript will be sent to external endpoint ({endpoint}).\n"
        "Set 'privacy_ack: true' in config.yaml to silence this warning.",
        err=True,
    )


def _write_atomic(path: Path, text: str, label: str) -> None:
    from utils import write_text_atomic  # noqa: PLC0415

    try:
        write_text_atomic(path, text)
    except OSError as exc:
        typer.echo(f"Error writing {label} to {path.resolve()}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _ensure_output(path: Path) -> None:
    if path.is_dir():
        typer.echo(f"Error: output path is a directory: {path}", err=True)
        raise typer.Exit(code=1)
    if not path.parent.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            typer.echo(f"Error creating output directory {path.parent}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        logger.info("Created output directory: %s", path.parent)


@app.command()
def batch(
    folder: Annotated[Path, typer.Argument(file_okay=False, dir_okay=True, help="Folder with audio files to process")],
    output_dir: Annotated[
        Path | None, typer.Option("-o", "--output-dir", help="Output directory (defaults to folder)")
    ] = None,
    mode: Annotated[str | None, typer.Option("-m", "--mode", help="Summary mode: brief | medium | detailed")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Model name (overrides config)")] = None,
    provider: Annotated[
        str | None, typer.Option("-p", "--provider", help="Provider: openai | xai | ollama | lm-studio | vllm")
    ] = None,
    language: Annotated[
        str | None, typer.Option("-l", "--language", help="Transcription language code (ru, en, …)")
    ] = None,
    summary_language: Annotated[
        str | None, typer.Option("--summary-language", help="Summary language (ru). Defaults to ru.")
    ] = None,
    output_format: Annotated[str, typer.Option("-f", "--format", help="Output format: telegram | json")] = "telegram",
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Process all audio files in a folder: transcribe and summarize each."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415
    from formatters import to_json, to_telegram  # noqa: PLC0415
    from preprocessing import prepared_audio  # noqa: PLC0415
    from providers.factory import make_summarizer, make_transcriber  # noqa: PLC0415
    from utils import write_text_atomic  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not folder.is_dir():
        typer.echo(f"Error: folder not found: {folder}", err=True)
        raise typer.Exit(code=1)

    provider_name = provider or settings.summarization.model.provider
    mode_name = mode or settings.summarization.mode
    lang = language or settings.transcription.language
    out_dir = output_dir or folder

    if output_format not in ("telegram", "json"):
        typer.echo(f"Unknown format: {output_format!r}. Available: telegram, json", err=True)
        raise typer.Exit(code=1)

    try:
        summarizer = make_summarizer(settings, provider_name, mode_name, model, summary_language)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    from workflows import AUDIO_EXTENSIONS  # noqa: PLC0415

    audio_files = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS)

    if not audio_files:
        typer.echo(f"No audio files found in {folder}.")
        return

    from collections import defaultdict  # noqa: PLC0415

    stem_map: defaultdict[str, list[Path]] = defaultdict(list)
    for p in audio_files:
        stem_map[p.stem].append(p)
    collisions = {stem: files for stem, files in stem_map.items() if len(files) > 1}
    if collisions:
        typer.echo("Error: output name collisions (same stem, different extension):", err=True)
        for stem, files in sorted(collisions.items()):
            typer.echo(f"  {stem!r}: {', '.join(f.name for f in files)}", err=True)
        raise typer.Exit(code=1)

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        typer.echo(f"Error creating output directory {out_dir}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _warn_if_external(
        settings.summarization.model.base_url or PROVIDER_PRESETS[provider_name], provider_name, settings.privacy_ack
    )

    try:
        transcriber = make_transcriber(settings)
    except Exception as exc:
        typer.echo(f"Error loading Whisper model: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    failures: list[tuple[Path, Exception]] = []
    succeeded = 0

    for audio_path in audio_files:
        typer.echo(f"\nProcessing: {audio_path.name}")
        transcript_path = out_dir / f"{audio_path.stem}.txt"
        summary_ext = ".json" if output_format == "json" else ".txt"
        summary_path = out_dir / f"{audio_path.stem}_summary{summary_ext}"
        try:
            with prepared_audio(audio_path, settings.preprocessing) as prepared:
                tr = transcriber.transcribe(prepared, lang)
            write_text_atomic(transcript_path, tr.to_file_format())
            if tr.is_empty:
                typer.echo("  No speech detected — summary skipped.", err=True)
                succeeded += 1
                continue
            raw = summarizer.summarize(tr.to_text())
            if output_format == "json":
                from models import MeetingSummary  # noqa: PLC0415

                write_text_atomic(summary_path, to_json(MeetingSummary(raw=raw, mode=mode_name)))
            else:
                write_text_atomic(summary_path, to_telegram(raw))
            succeeded += 1
        except Exception as exc:
            typer.echo(f"  Error: {exc}", err=True)
            failures.append((audio_path, exc))

    typer.echo(f"\n{succeeded} succeeded, {len(failures)} failed.")
    if failures:
        raise typer.Exit(code=1)


@app.command()
def preprocess(
    audio: Annotated[Path | None, typer.Argument(file_okay=True, dir_okay=False, help="Audio file to preprocess")] = None,
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output WAV file")] = None,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Preprocess audio to a stable WAV format using ffmpeg."""
    from config import ConfigError, Settings  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    audio_path = audio or settings.audio
    if not audio_path.exists():
        typer.echo(f"Error: audio file not found: {audio_path}", err=True)
        raise typer.Exit(code=1)

    output_path = output or audio_path.with_name(f"{audio_path.stem}.preprocessed.wav")
    _ensure_output(output_path)
    logger.info("Preprocessing: %s → %s", audio_path, output_path)

    try:
        from preprocessing import preprocess_audio  # noqa: PLC0415

        preprocess_audio(audio_path, output_path, settings.preprocessing)
    except Exception as exc:
        typer.echo(f"Preprocessing error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Preprocessed audio saved to {output_path}")


@app.command()
def transcribe(
    audio: Annotated[Path | None, typer.Argument(file_okay=True, dir_okay=False, help="Audio file to process")] = None,
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output transcript file")] = None,
    language: Annotated[str | None, typer.Option("-l", "--language", help="Language code (ru, en, …)")] = None,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Transcribe an audio file to a timestamped transcript."""
    from config import ConfigError, Settings  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    audio_path = audio or settings.audio
    if not audio_path.exists():
        typer.echo(f"Error: audio file not found: {audio_path}", err=True)
        raise typer.Exit(code=1)
    output_path = output or settings.transcript
    lang = language or settings.transcription.language
    _ensure_output(output_path)
    logger.info("Transcribing: %s", audio_path)
    try:
        from providers.factory import make_transcriber  # noqa: PLC0415

        transcriber = make_transcriber(settings)
    except Exception as exc:
        typer.echo(f"Error loading Whisper model: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        from preprocessing import prepared_audio  # noqa: PLC0415

        with prepared_audio(audio_path, settings.preprocessing) as prepared:
            transcript = transcriber.transcribe(prepared, lang)
    except Exception as exc:
        typer.echo(f"Transcription error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    logger.info("Writing transcript to %s", output_path.resolve())
    _write_atomic(output_path, transcript.to_file_format(), "transcript")
    typer.echo(f"Transcript saved to {output_path}")


@app.command()
def summarize(
    transcript: Annotated[
        Path | None, typer.Argument(file_okay=True, dir_okay=False, help="Transcript file to summarize")
    ] = None,
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output summary file")] = None,
    mode: Annotated[str | None, typer.Option("-m", "--mode", help="Summary mode: brief | medium | detailed")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Model name (overrides config)")] = None,
    provider: Annotated[
        str | None, typer.Option("-p", "--provider", help="Provider: openai | xai | ollama | lm-studio | vllm")
    ] = None,
    summary_language: Annotated[
        str | None,
        typer.Option("--summary-language", help="Summary language (ru). Defaults to ru."),
    ] = None,
    output_format: Annotated[str, typer.Option("-f", "--format", help="Output format: telegram | json")] = "telegram",
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Generate a meeting summary from a transcript."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    transcript_path = transcript or settings.transcript
    if not transcript_path.exists():
        typer.echo(f"Error: transcript file not found: {transcript_path}", err=True)
        raise typer.Exit(code=1)
    output_path = output or settings.summary
    provider_name = provider or settings.summarization.model.provider
    mode_name = mode or settings.summarization.mode

    if output_format not in ("telegram", "json"):
        typer.echo(f"Unknown format: {output_format!r}. Available: telegram, json", err=True)
        raise typer.Exit(code=1)

    try:
        from providers.factory import make_summarizer  # noqa: PLC0415

        summarizer = make_summarizer(settings, provider_name, mode_name, model, summary_language)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    _ensure_output(output_path)
    logger.info("Summarizing: %s via %s (mode: %s)", transcript_path, provider_name, mode_name)

    from formatters import to_json, to_telegram  # noqa: PLC0415
    from transcript import Transcript  # noqa: PLC0415

    try:
        tr = Transcript.from_file(transcript_path)
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo(f"Error reading transcript: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if tr.is_empty:
        typer.echo("Error: no speech detected in transcript.", err=True)
        raise typer.Exit(code=1)

    _warn_if_external(
        settings.summarization.model.base_url or PROVIDER_PRESETS[provider_name], provider_name, settings.privacy_ack
    )

    try:
        raw = summarizer.summarize(tr.to_text())
        if output_format == "json":
            from models import MeetingSummary  # noqa: PLC0415

            formatted = to_json(MeetingSummary(raw=raw, mode=mode_name))
        else:
            formatted = to_telegram(raw)
    except Exception as exc:
        typer.echo(f"LLM error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(formatted)
    logger.info("Writing summary to %s", output_path.resolve())
    _write_atomic(output_path, formatted, "summary")
    typer.echo(f"\nSummary saved to {output_path}", err=output_format == "json")


@app.command()
def run(
    audio: Annotated[Path | None, typer.Argument(file_okay=True, dir_okay=False, help="Audio file to process")] = None,
    language: Annotated[
        str | None, typer.Option("-l", "--language", help="Transcription language code (ru, en, …)")
    ] = None,
    summary_language: Annotated[
        str | None, typer.Option("--summary-language", help="Summary language (ru). Defaults to ru.")
    ] = None,
    mode: Annotated[str | None, typer.Option("-m", "--mode", help="Summary mode: brief | medium | detailed")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Model name (overrides config)")] = None,
    provider: Annotated[str | None, typer.Option("-p", "--provider")] = None,
    transcript: Annotated[Path | None, typer.Option("--transcript")] = None,
    summary: Annotated[Path | None, typer.Option("--summary")] = None,
    output_format: Annotated[str, typer.Option("-f", "--format", help="Output format: telegram | json")] = "telegram",
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Run the full pipeline: transcribe audio, then summarize."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415
    from formatters import to_json, to_telegram  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    audio_path = audio or settings.audio
    if not audio_path.exists():
        typer.echo(f"Error: audio file not found: {audio_path}", err=True)
        raise typer.Exit(code=1)

    transcript_path = transcript or settings.transcript
    summary_path = summary or settings.summary
    provider_name = provider or settings.summarization.model.provider
    mode_name = mode or settings.summarization.mode

    if output_format not in ("telegram", "json"):
        typer.echo(f"Unknown format: {output_format!r}. Available: telegram, json", err=True)
        raise typer.Exit(code=1)

    try:
        from providers.factory import make_summarizer, make_transcriber  # noqa: PLC0415

        summarizer = make_summarizer(settings, provider_name, mode_name, model, summary_language)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    _ensure_output(transcript_path)
    _ensure_output(summary_path)

    try:
        transcriber = make_transcriber(settings)
    except Exception as exc:
        typer.echo(f"Error loading Whisper model: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        from preprocessing import prepared_audio  # noqa: PLC0415

        with prepared_audio(audio_path, settings.preprocessing) as prepared:
            tr = transcriber.transcribe(prepared, language or settings.transcription.language)
    except Exception as exc:
        typer.echo(f"Transcription error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _write_atomic(transcript_path, tr.to_file_format(), "transcript")
    typer.echo(f"Transcript saved to {transcript_path}", err=output_format == "json")

    if tr.is_empty:
        typer.echo("No speech detected in transcript — summary skipped.", err=True)
        raise typer.Exit(code=1)

    _warn_if_external(
        settings.summarization.model.base_url or PROVIDER_PRESETS[provider_name], provider_name, settings.privacy_ack
    )

    try:
        raw = summarizer.summarize(tr.to_text())
        if output_format == "json":
            from models import MeetingSummary  # noqa: PLC0415

            formatted = to_json(MeetingSummary(raw=raw, mode=mode_name))
        else:
            formatted = to_telegram(raw)
    except Exception as exc:
        typer.echo(f"LLM error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(formatted)
    _write_atomic(summary_path, formatted, "summary")
    typer.echo(f"\nSummary saved to {summary_path}", err=output_format == "json")
