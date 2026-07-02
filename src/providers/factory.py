from __future__ import annotations

from typing import TYPE_CHECKING

from config import PROVIDER_PRESETS, TRANSCRIBER_PROVIDERS, Settings

if TYPE_CHECKING:
    from providers.llm import LLMSummarizer
    from providers.whisper import WhisperTranscriber


def make_summarizer(
    settings: Settings,
    provider_name: str,
    mode_name: str,
    model_override: str | None = None,
    summary_language: str | None = None,
) -> LLMSummarizer:
    """Validate provider, mode, and language, then build an LLMSummarizer.

    Raises ValueError for unknown provider, mode, or language.
    """
    from prompts import CHUNK_PROMPTS, get_prompt  # noqa: PLC0415

    if provider_name not in PROVIDER_PRESETS:
        available = ", ".join(PROVIDER_PRESETS)
        raise ValueError(f"Unknown provider: {provider_name!r}. Available: {available}")

    summarization = settings.summarization
    model = summarization.model

    # Default to "ru" — the only language with prompt content shipped.
    # transcription.language is NOT inherited here so that -l en (English audio)
    # still produces a Russian summary without requiring --summary-language ru.
    effective_lang = summary_language or summarization.language or "ru"
    try:
        prompt_template = get_prompt(effective_lang, mode_name)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    chunk_prompt = CHUNK_PROMPTS.get(effective_lang, CHUNK_PROMPTS["ru"])

    # An external (non-local) endpoint must have an explicit key. Without one the
    # OpenAI SDK would silently read OPENAI_API_KEY from the environment — the exact
    # fallback the project documents as absent — so fail loudly instead.
    from workflows import is_external_provider  # noqa: PLC0415

    resolved_base_url = model.base_url or PROVIDER_PRESETS[provider_name]
    if is_external_provider(resolved_base_url, provider_name) and not model.api_key:
        raise ValueError(
            "No API key configured for external provider "
            f"{provider_name!r}. Set summarization.model.api_key or the "
            "RECAP_SUMMARIZATION_MODEL_API_KEY environment variable."
        )

    from providers.llm import LLMSummarizer  # noqa: PLC0415

    return LLMSummarizer(
        model=model_override or model.name,
        api_key=model.api_key,
        base_url=resolved_base_url,
        max_chars=summarization.max_transcript_chars,
        prompt_template=prompt_template,
        chunk_prompt=chunk_prompt,
        timeout=summarization.timeout_seconds,
        max_retries=summarization.retries,
        chunking_mode=summarization.chunking_mode,
        num_ctx=model.num_ctx,
    )


def make_transcriber(settings: Settings) -> WhisperTranscriber:
    """Build a WhisperTranscriber from settings.

    Raises ValueError for an unsupported transcription provider.
    """
    model = settings.transcription.model
    if model.provider not in TRANSCRIBER_PROVIDERS:
        available = ", ".join(sorted(TRANSCRIBER_PROVIDERS))
        raise ValueError(f"Unknown transcription provider: {model.provider!r}. Available: {available}")

    from providers.whisper import WhisperTranscriber  # noqa: PLC0415

    return WhisperTranscriber(
        model_name=model.name,
        device=model.device,
        compute_type=model.compute_type,
        beam_size=model.beam_size,
        vad_filter=model.vad_filter,
        condition_on_previous_text=model.condition_on_previous_text,
    )
