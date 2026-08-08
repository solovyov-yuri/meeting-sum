from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROVIDER_PRESETS: dict[str, str | None] = {
    "openai": None,
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "lm-studio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
}

TRANSCRIBER_PROVIDERS: frozenset[str] = frozenset({"faster-whisper"})

_VALID_WHISPER_DEVICES = {"cuda", "cpu", "auto"}
_VALID_WHISPER_COMPUTE_TYPES = {"default", "float16", "int8", "int8_float16", "float32"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TranscriptionModelSettings:
    provider: str = "faster-whisper"
    name: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "default"
    beam_size: int = 5
    vad_filter: bool = True
    condition_on_previous_text: bool = True


@dataclass(frozen=True)
class TranscriptionSettings:
    language: str = "ru"
    model: TranscriptionModelSettings = field(default_factory=TranscriptionModelSettings)


@dataclass(frozen=True)
class SummarizationModelSettings:
    provider: str = "ollama"
    name: str = "qwen3.5:latest"
    api_key: str | None = None
    base_url: str | None = None
    # Ollama context window in tokens (options.num_ctx). null = model default; ignored by OpenAI/xAI.
    num_ctx: int | None = None


@dataclass(frozen=True)
class SummarizationSettings:
    # language defaults to None → factory falls back to "ru". The transcription
    # language is deliberately NOT inherited, so English audio still yields a
    # Russian summary unless summarization.language is set explicitly.
    language: str | None = None
    mode: str = "medium"
    max_transcript_chars: int = 42_000
    timeout_seconds: float = 60.0
    retries: int = 2
    chunking_mode: str = "chunk"
    model: SummarizationModelSettings = field(default_factory=SummarizationModelSettings)


@dataclass(frozen=True)
class PreprocessingSettings:
    enabled: bool = False
    sample_rate: int = 16000
    channels: int = 1
    codec: str = "pcm_s16le"
    loudness_normalization: bool = False
    target_lufs: float = -16.0
    true_peak_db: float = -1.5
    loudness_range: float = 11.0
    highpass_hz: int | None = None
    keep_temp: bool = False


# ── Schema: allowed keys per section ────────────────────────────────────────────

_TOP_LEVEL_KEYS = {
    "audio",
    "transcript",
    "summary",
    "output_dir",
    "transcription",
    "summarization",
    "privacy_ack",
    "preprocessing",
}
_TRANSCRIPTION_KEYS = {"language", "model"}
_TRANSCRIPTION_MODEL_KEYS = {
    "provider",
    "name",
    "device",
    "compute_type",
    "beam_size",
    "vad_filter",
    "condition_on_previous_text",
}
_SUMMARIZATION_KEYS = {
    "language",
    "mode",
    "max_transcript_chars",
    "timeout_seconds",
    "retries",
    "chunking_mode",
    "model",
}
_SUMMARIZATION_MODEL_KEYS = {"provider", "name", "api_key", "base_url", "num_ctx"}
_PREPROCESSING_KEYS = {
    "enabled",
    "sample_rate",
    "channels",
    "codec",
    "loudness_normalization",
    "target_lufs",
    "true_peak_db",
    "loudness_range",
    "highpass_hz",
    "keep_temp",
}

# ── Environment variable maps (one per section) ─────────────────────────────────

_ENV_TOP = {
    "RECAP_AUDIO": "audio",
    "RECAP_TRANSCRIPT": "transcript",
    "RECAP_SUMMARY": "summary",
    "RECAP_OUTPUT_DIR": "output_dir",
    "RECAP_PRIVACY_ACK": "privacy_ack",
}
_ENV_TRANSCRIPTION = {
    "RECAP_TRANSCRIPTION_LANGUAGE": "language",
}
_ENV_TRANSCRIPTION_MODEL = {
    "RECAP_TRANSCRIPTION_MODEL_PROVIDER": "provider",
    "RECAP_TRANSCRIPTION_MODEL_NAME": "name",
    "RECAP_TRANSCRIPTION_MODEL_DEVICE": "device",
    "RECAP_TRANSCRIPTION_MODEL_COMPUTE_TYPE": "compute_type",
    "RECAP_TRANSCRIPTION_MODEL_BEAM_SIZE": "beam_size",
    "RECAP_TRANSCRIPTION_MODEL_VAD_FILTER": "vad_filter",
    "RECAP_TRANSCRIPTION_MODEL_CONDITION_ON_PREVIOUS_TEXT": "condition_on_previous_text",
}
_ENV_SUMMARIZATION = {
    "RECAP_SUMMARIZATION_LANGUAGE": "language",
    "RECAP_SUMMARIZATION_MODE": "mode",
    "RECAP_SUMMARIZATION_MAX_TRANSCRIPT_CHARS": "max_transcript_chars",
    "RECAP_SUMMARIZATION_TIMEOUT_SECONDS": "timeout_seconds",
    "RECAP_SUMMARIZATION_RETRIES": "retries",
    "RECAP_SUMMARIZATION_CHUNKING_MODE": "chunking_mode",
}
_ENV_SUMMARIZATION_MODEL = {
    "RECAP_SUMMARIZATION_MODEL_PROVIDER": "provider",
    "RECAP_SUMMARIZATION_MODEL_NAME": "name",
    "RECAP_SUMMARIZATION_MODEL_API_KEY": "api_key",
    "RECAP_SUMMARIZATION_MODEL_BASE_URL": "base_url",
    "RECAP_SUMMARIZATION_MODEL_NUM_CTX": "num_ctx",
}
_ENV_PREPROCESSING = {
    "RECAP_PREPROCESSING_ENABLED": "enabled",
    "RECAP_PREPROCESSING_SAMPLE_RATE": "sample_rate",
    "RECAP_PREPROCESSING_CHANNELS": "channels",
    "RECAP_PREPROCESSING_CODEC": "codec",
    "RECAP_PREPROCESSING_LOUDNESS_NORMALIZATION": "loudness_normalization",
    "RECAP_PREPROCESSING_TARGET_LUFS": "target_lufs",
    "RECAP_PREPROCESSING_TRUE_PEAK_DB": "true_peak_db",
    "RECAP_PREPROCESSING_LOUDNESS_RANGE": "loudness_range",
    "RECAP_PREPROCESSING_HIGHPASS_HZ": "highpass_hz",
    "RECAP_PREPROCESSING_KEEP_TEMP": "keep_temp",
}

_TRUE_STRINGS = ("true", "1", "yes")


# ── Coercion helpers (operate in place on a working dict) ────────────────────────


def _coerce_bool(d: dict, key: str) -> None:
    if key in d:
        val = d[key]
        d[key] = val.lower() in _TRUE_STRINGS if isinstance(val, str) else bool(val)


def _coerce_positive_int(d: dict, key: str, label: str) -> None:
    if key not in d:
        return
    try:
        d[key] = int(d[key])
    except (ValueError, TypeError):
        raise ConfigError(f"'{label}' must be a positive integer, got {d[key]!r}")
    if d[key] <= 0:
        raise ConfigError(f"'{label}' must be a positive integer, got {d[key]}")


def _coerce_section(raw: dict, key: str) -> dict:
    """Return a shallow copy of a nested mapping section, validating its type."""
    section = raw.get(key)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ConfigError(f"'{key}' must be a mapping, got {type(section).__name__}")
    return dict(section)


def _reject_unknown(data: dict, allowed: set[str], prefix: str) -> None:
    for key in data:
        if key in allowed:
            continue
        location = f"{prefix}.{key}" if prefix else key
        raise ConfigError(f"Unknown config key: {location!r}.")


def _apply_env(data: dict, env_map: dict[str, str]) -> None:
    for env_var, key in env_map.items():
        if (value := os.environ.get(env_var)) is not None:
            data[key] = value


@dataclass(frozen=True)
class Settings:
    audio: Path = Path("data/meeting.wav")
    transcript: Path = Path("data/transcript.txt")
    summary: Path = Path("data/summary.txt")
    # Desktop-only: a single folder for all run outputs (transcript + summary), named by audio stem.
    # null → outputs land next to the audio file. The CLI keeps its per-file transcript/summary
    # defaults above (deliberate CLI/desktop divergence — the desktop UI exposes only this folder).
    output_dir: Path | None = None
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    summarization: SummarizationSettings = field(default_factory=SummarizationSettings)
    preprocessing: PreprocessingSettings = field(default_factory=PreprocessingSettings)
    privacy_ack: bool = False

    @classmethod
    def load(cls, config_path: Path = Path("config.yaml")) -> Settings:
        raw: dict = {}

        if config_path.exists():
            import yaml  # noqa: PLC0415

            with config_path.open(encoding="utf-8") as f:
                try:
                    parsed = yaml.safe_load(f)
                except yaml.YAMLError as exc:
                    raise ConfigError(f"config.yaml is not valid YAML: {exc}") from exc
            if parsed is not None and not isinstance(parsed, dict):
                raise ConfigError(f"config.yaml must be a YAML mapping, got {type(parsed).__name__}")
            raw = parsed or {}

        _reject_unknown(raw, _TOP_LEVEL_KEYS, prefix="")

        top = {k: raw[k] for k in ("audio", "transcript", "summary", "output_dir", "privacy_ack") if k in raw}
        transcription = _coerce_section(raw, "transcription")
        transcription_model = _coerce_section(transcription, "model")
        summarization = _coerce_section(raw, "summarization")
        summarization_model = _coerce_section(summarization, "model")
        preprocessing = _coerce_section(raw, "preprocessing")

        _reject_unknown(transcription, _TRANSCRIPTION_KEYS, prefix="transcription")
        _reject_unknown(transcription_model, _TRANSCRIPTION_MODEL_KEYS, prefix="transcription.model")
        _reject_unknown(summarization, _SUMMARIZATION_KEYS, prefix="summarization")
        _reject_unknown(summarization_model, _SUMMARIZATION_MODEL_KEYS, prefix="summarization.model")
        _reject_unknown(preprocessing, _PREPROCESSING_KEYS, prefix="preprocessing")
        transcription.pop("model", None)
        summarization.pop("model", None)

        _apply_env(top, _ENV_TOP)
        _apply_env(transcription, _ENV_TRANSCRIPTION)
        _apply_env(transcription_model, _ENV_TRANSCRIPTION_MODEL)
        _apply_env(summarization, _ENV_SUMMARIZATION)
        _apply_env(summarization_model, _ENV_SUMMARIZATION_MODEL)
        _apply_env(preprocessing, _ENV_PREPROCESSING)

        # ── Coerce + validate ───────────────────────────────────────────────────
        for path_field in ("audio", "transcript", "summary", "output_dir"):
            # output_dir may be explicitly null (→ leave as None); the others always have a value.
            if path_field in top and top[path_field] is not None:
                try:
                    top[path_field] = Path(top[path_field])
                except TypeError:
                    raise ConfigError(f"'{path_field}' must be a file path string, got {top[path_field]!r}")

        _coerce_bool(top, "privacy_ack")
        _coerce_bool(transcription_model, "vad_filter")
        _coerce_bool(transcription_model, "condition_on_previous_text")
        _coerce_positive_int(transcription_model, "beam_size", "transcription.model.beam_size")
        _coerce_positive_int(summarization, "max_transcript_chars", "summarization.max_transcript_chars")

        if "timeout_seconds" in summarization:
            try:
                summarization["timeout_seconds"] = float(summarization["timeout_seconds"])
            except (ValueError, TypeError):
                raise ConfigError(
                    f"'summarization.timeout_seconds' must be a number, got {summarization['timeout_seconds']!r}"
                )
            if summarization["timeout_seconds"] <= 0:
                raise ConfigError(
                    f"'summarization.timeout_seconds' must be positive, got {summarization['timeout_seconds']}"
                )

        if "retries" in summarization:
            try:
                summarization["retries"] = int(summarization["retries"])
            except (ValueError, TypeError):
                raise ConfigError(
                    f"'summarization.retries' must be a non-negative integer, got {summarization['retries']!r}"
                )
            if summarization["retries"] < 0:
                raise ConfigError(f"'summarization.retries' must be >= 0, got {summarization['retries']}")

        if (provider := transcription_model.get("provider")) is not None and provider not in TRANSCRIBER_PROVIDERS:
            available = ", ".join(sorted(TRANSCRIBER_PROVIDERS))
            raise ConfigError(f"'transcription.model.provider' must be one of: {available}. Got {provider!r}")

        if (device := transcription_model.get("device")) is not None and device not in _VALID_WHISPER_DEVICES:
            available = ", ".join(sorted(_VALID_WHISPER_DEVICES))
            raise ConfigError(f"'transcription.model.device' must be one of: {available}. Got {device!r}")

        if (
            compute_type := transcription_model.get("compute_type")
        ) is not None and compute_type not in _VALID_WHISPER_COMPUTE_TYPES:
            available = ", ".join(sorted(_VALID_WHISPER_COMPUTE_TYPES))
            raise ConfigError(f"'transcription.model.compute_type' must be one of: {available}. Got {compute_type!r}")

        if (chunking := summarization.get("chunking_mode")) is not None and chunking not in ("chunk", "truncate"):
            raise ConfigError(f"'summarization.chunking_mode' must be 'chunk' or 'truncate'. Got {chunking!r}")

        if (sum_provider := summarization_model.get("provider")) is not None and sum_provider not in PROVIDER_PRESETS:
            available = ", ".join(PROVIDER_PRESETS)
            raise ConfigError(f"'summarization.model.provider' must be one of: {available}. Got {sum_provider!r}")

        if "num_ctx" in summarization_model and summarization_model["num_ctx"] is not None:
            _coerce_positive_int(summarization_model, "num_ctx", "summarization.model.num_ctx")

        if (mode := summarization.get("mode")) is not None:
            from prompts import SUMMARY_MODES  # noqa: PLC0415

            if mode not in SUMMARY_MODES:
                available = ", ".join(sorted(SUMMARY_MODES))
                raise ConfigError(f"'summarization.mode' must be one of: {available}. Got {mode!r}")

        if (lang := summarization.get("language")) is not None:
            from prompts import PROMPTS  # noqa: PLC0415

            if lang not in PROMPTS:
                available = ", ".join(sorted(PROMPTS))
                raise ConfigError(f"'summarization.language' must be one of: {available}. Got {lang!r}")

        # ── Preprocessing coerce + validate ─────────────────────────────────────
        _coerce_bool(preprocessing, "enabled")
        _coerce_bool(preprocessing, "loudness_normalization")
        _coerce_bool(preprocessing, "keep_temp")
        _coerce_positive_int(preprocessing, "sample_rate", "preprocessing.sample_rate")
        _coerce_positive_int(preprocessing, "channels", "preprocessing.channels")
        if (channels := preprocessing.get("channels")) is not None and channels not in (1, 2):
            raise ConfigError(f"'preprocessing.channels' must be 1 or 2, got {channels}")

        if (codec := preprocessing.get("codec")) is not None and codec != "pcm_s16le":
            raise ConfigError(f"'preprocessing.codec' must be 'pcm_s16le'. Got {codec!r}")

        for float_field in ("target_lufs", "true_peak_db", "loudness_range"):
            if float_field in preprocessing:
                try:
                    preprocessing[float_field] = float(preprocessing[float_field])
                except (ValueError, TypeError):
                    raise ConfigError(
                        f"'preprocessing.{float_field}' must be a number, got {preprocessing[float_field]!r}"
                    )

        if "highpass_hz" in preprocessing:
            val = preprocessing["highpass_hz"]
            if val is not None:
                try:
                    preprocessing["highpass_hz"] = int(val)
                except (ValueError, TypeError):
                    raise ConfigError(
                        f"'preprocessing.highpass_hz' must be a positive integer or null, got {val!r}"
                    )
                if preprocessing["highpass_hz"] <= 0:
                    raise ConfigError(
                        f"'preprocessing.highpass_hz' must be a positive integer, got {preprocessing['highpass_hz']}"
                    )

        return cls(
            **top,
            transcription=TranscriptionSettings(
                **transcription,
                model=TranscriptionModelSettings(**transcription_model),
            ),
            summarization=SummarizationSettings(
                **summarization,
                model=SummarizationModelSettings(**summarization_model),
            ),
            preprocessing=PreprocessingSettings(**preprocessing),
        )
