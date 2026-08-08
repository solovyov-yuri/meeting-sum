from __future__ import annotations

import logging
import sys
from io import TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from workflows import ProgressEvent, RunResult

if isinstance(sys.stdout, TextIOWrapper):
    sys.stdout.reconfigure(write_through=True)

app = typer.Typer(help="Meeting transcription and summarization tool")
logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    # Non-verbose: suppress workflow ERROR tracebacks (the user-facing message already comes back
    # via RunResult); -v surfaces the full technical detail.
    logging.basicConfig(
        level=logging.INFO if verbose else logging.CRITICAL,
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


def _run_progress(event: ProgressEvent) -> None:
    """Render a workflow progress event as a CLI progress line on stderr."""
    typer.echo(f"[{event.step}] {event.message}", err=True)


def _finish_run(result: RunResult) -> None:
    """Map a workflow ``RunResult`` to CLI stdout/stderr + exit code.

    Success → echo the summary to stdout; any non-success → the (Russian) error message to
    stderr and exit 1. Used by ``run`` (``summarize`` handles its own stdout to keep ``-f json``).
    """
    if result.status == "success":
        if result.summary_text:
            typer.echo(result.summary_text)
        if result.summary_path:
            typer.echo(f"Сохранено: {result.summary_path}", err=True)
        return
    typer.echo(result.error_message or "Ошибка.", err=True)
    raise typer.Exit(code=1)


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
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Process all audio files in a folder: transcribe and summarize each (writes .txt + .json)."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415
    from workflows import AUDIO_EXTENSIONS, RunOptions, run_one_file  # noqa: PLC0415

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
    out_dir = output_dir or folder

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
        settings.summarization.model.base_url or PROVIDER_PRESETS.get(provider_name), provider_name, settings.privacy_ack
    )

    # Cache the transcriber across files so batch keeps loading the model only once (PERF-001 factory).
    from providers.whisper import WhisperTranscriber  # noqa: PLC0415

    _cache: dict[str, WhisperTranscriber] = {}

    def _transcriber_factory(s: Settings) -> WhisperTranscriber:
        from providers.factory import make_transcriber  # noqa: PLC0415

        if "t" not in _cache:
            _cache["t"] = make_transcriber(s)
        return _cache["t"]

    succeeded = 0
    failed = 0
    for audio_path in audio_files:
        typer.echo(f"\nProcessing: {audio_path.name}", err=True)
        options = RunOptions(
            audio_path=audio_path,
            transcript_path=out_dir / f"{audio_path.stem}.txt",
            summary_path=out_dir / f"{audio_path.stem}_summary.txt",
            transcription_language=language,
            summary_language=summary_language,
            provider=provider,
            model=model,
            mode=mode,
        )
        result = run_one_file(options, settings=settings, progress=_run_progress, transcriber_factory=_transcriber_factory)
        if result.status == "success":
            succeeded += 1
        else:
            typer.echo(f"  {result.error_message}", err=True)
            failed += 1

    typer.echo(f"\n{succeeded} succeeded, {failed} failed.")
    if failed:
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
    output_format: Annotated[
        str, typer.Option("-f", "--format", help="Which format to echo to stdout: markdown | json (both files are written)")
    ] = "markdown",
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show progress logs")] = False,
) -> None:
    """Generate a meeting summary from a transcript (writes .txt + .json)."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415
    from workflows import RunOptions, resummarize_one  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_format not in ("markdown", "json"):
        typer.echo(f"Unknown format: {output_format!r}. Available: markdown, json", err=True)
        raise typer.Exit(code=1)

    provider_name = provider or settings.summarization.model.provider
    _warn_if_external(
        settings.summarization.model.base_url or PROVIDER_PRESETS.get(provider_name), provider_name, settings.privacy_ack
    )
    options = RunOptions(
        transcript_path=transcript,
        summary_path=output,
        summary_language=summary_language,
        provider=provider,
        model=model,
        mode=mode,
    )
    result = resummarize_one(options, settings=settings, progress=_run_progress)

    if result.status != "success":
        typer.echo(result.error_message or "Ошибка.", err=True)
        raise typer.Exit(code=1)

    # Both .txt and .json are written; -f only chooses what goes to stdout (keeps `-f json | jq`).
    if output_format == "json" and result.summary_json_path:
        typer.echo(Path(result.summary_json_path).read_text(encoding="utf-8"))
    elif result.summary_text:
        typer.echo(result.summary_text)
    if result.summary_path:
        typer.echo(f"Сохранено: {result.summary_path}", err=True)


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
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Run the full pipeline: transcribe audio, then summarize (writes .txt + .json)."""
    from config import PROVIDER_PRESETS, ConfigError, Settings  # noqa: PLC0415
    from workflows import RunOptions, run_one_file  # noqa: PLC0415

    _configure_logging(verbose)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    provider_name = provider or settings.summarization.model.provider
    _warn_if_external(
        settings.summarization.model.base_url or PROVIDER_PRESETS.get(provider_name), provider_name, settings.privacy_ack
    )
    options = RunOptions(
        audio_path=audio or settings.audio,
        transcript_path=transcript,
        summary_path=summary,
        transcription_language=language,
        summary_language=summary_language,
        provider=provider,
        model=model,
        mode=mode,
    )
    result = run_one_file(options, settings=settings, progress=_run_progress)
    _finish_run(result)
