from pathlib import Path

import pytest

from config import (
    ConfigError,
    PreprocessingSettings,
    Settings,
    SummarizationModelSettings,
    SummarizationSettings,
    TranscriptionModelSettings,
    TranscriptionSettings,
)

# ── Defaults ────────────────────────────────────────────────────────────────────


def test_defaults_produce_nested_settings() -> None:
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert isinstance(s.transcription, TranscriptionSettings)
    assert isinstance(s.transcription.model, TranscriptionModelSettings)
    assert isinstance(s.summarization, SummarizationSettings)
    assert isinstance(s.summarization.model, SummarizationModelSettings)

    assert s.transcription.language == "ru"
    assert s.transcription.model.provider == "faster-whisper"
    assert s.transcription.model.name == "large-v3"
    assert s.summarization.language is None
    assert s.summarization.mode == "medium"
    assert s.summarization.max_transcript_chars == 42_000
    assert s.summarization.model.provider == "ollama"
    assert s.summarization.model.name == "qwen3.5:latest"
    assert s.summarization.model.api_key is None
    assert s.privacy_ack is False


def test_settings_is_immutable() -> None:
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    with pytest.raises(AttributeError):
        s.privacy_ack = True  # type: ignore[misc]
    with pytest.raises(AttributeError):
        s.summarization.model.provider = "openai"  # type: ignore[misc]


# ── Nested YAML loading ─────────────────────────────────────────────────────────


def test_nested_yaml_loads(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "transcription:\n"
        "  language: en\n"
        "  model:\n"
        "    name: medium\n"
        "    device: cpu\n"
        "summarization:\n"
        "  mode: brief\n"
        "  max_transcript_chars: 30000\n"
        "  model:\n"
        "    provider: openai\n"
        "    name: gpt-4o\n",
        encoding="utf-8",
    )
    s = Settings.load(config_path=cfg)
    assert s.transcription.language == "en"
    assert s.transcription.model.name == "medium"
    assert s.transcription.model.device == "cpu"
    assert s.summarization.mode == "brief"
    assert s.summarization.max_transcript_chars == 30000
    assert s.summarization.model.provider == "openai"
    assert s.summarization.model.name == "gpt-4o"


def test_path_fields_converted(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("audio: custom/meeting.wav\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert isinstance(s.audio, Path)
    assert s.audio == Path("custom/meeting.wav")


def test_partial_nested_section_uses_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  mode: brief\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert s.summarization.mode == "brief"
    # untouched nested fields keep their defaults
    assert s.summarization.model.provider == "ollama"
    assert s.transcription.model.name == "large-v3"


# ── Env var overrides ───────────────────────────────────────────────────────────


def test_env_overrides_nested_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_NAME", "gpt-4o")
    monkeypatch.setenv("RECAP_TRANSCRIPTION_LANGUAGE", "en")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.name == "gpt-4o"
    assert s.transcription.language == "en"


def test_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    name: from-yaml\n", encoding="utf-8")
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_NAME", "from-env")
    s = Settings.load(config_path=cfg)
    assert s.summarization.model.name == "from-env"


def test_env_transcription_model_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_TRANSCRIPTION_MODEL_NAME", "small")
    monkeypatch.setenv("RECAP_TRANSCRIPTION_MODEL_DEVICE", "cpu")
    monkeypatch.setenv("RECAP_TRANSCRIPTION_MODEL_BEAM_SIZE", "3")
    monkeypatch.setenv("RECAP_TRANSCRIPTION_MODEL_VAD_FILTER", "false")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.transcription.model.name == "small"
    assert s.transcription.model.device == "cpu"
    assert s.transcription.model.beam_size == 3
    assert s.transcription.model.vad_filter is False


def test_env_summarization_tuning_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("RECAP_SUMMARIZATION_RETRIES", "0")
    monkeypatch.setenv("RECAP_SUMMARIZATION_CHUNKING_MODE", "truncate")
    monkeypatch.setenv("RECAP_SUMMARIZATION_MAX_TRANSCRIPT_CHARS", "30000")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.timeout_seconds == 120.0
    assert s.summarization.retries == 0
    assert s.summarization.chunking_mode == "truncate"
    assert s.summarization.max_transcript_chars == 30000


def test_num_ctx_defaults_to_none() -> None:
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.num_ctx is None


def test_num_ctx_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_NUM_CTX", "32768")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.num_ctx == 32768


def test_num_ctx_from_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    num_ctx: 8192\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert s.summarization.model.num_ctx == 8192


def test_num_ctx_rejects_non_positive(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    num_ctx: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="summarization.model.num_ctx"):
        Settings.load(config_path=cfg)


def test_privacy_ack_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_PRIVACY_ACK", "true")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.privacy_ack is True


# ── API key ─────────────────────────────────────────────────────────────────────


def test_openai_api_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    # No implicit OPENAI_API_KEY fallback: the key is set only via
    # summarization.model.api_key (config) or RECAP_SUMMARIZATION_MODEL_API_KEY.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("RECAP_SUMMARIZATION_MODEL_API_KEY", raising=False)
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.api_key is None


def test_recap_api_key_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_API_KEY", "sk-custom")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.api_key == "sk-custom"


# ── Unknown / legacy keys hard-fail ─────────────────────────────────────────────


def test_unknown_top_level_key_fails(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("bogus: value\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown config key: 'bogus'"):
        Settings.load(config_path=cfg)


def test_unknown_nested_key_fails(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    bogus: value\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="summarization.model.bogus"):
        Settings.load(config_path=cfg)


@pytest.mark.parametrize(
    "old_key",
    [
        "provider",
        "model",
        "whisper_model",
        "summary_mode",
        "max_transcript_chars",
        "transcription_language",
        "language",
        "summary_language",
        "llm_timeout_seconds",
        "chunking_mode",
    ],
)
def test_legacy_flat_key_rejected(tmp_path: Path, old_key: str) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"{old_key}: somevalue\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=rf"Unknown config key: '{old_key}'") as exc:
        Settings.load(config_path=cfg)
    # Generic failure: no per-key migration hint.
    assert "instead" not in str(exc.value)


# ── Malformed YAML ──────────────────────────────────────────────────────────────


def test_malformed_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("key: [unclosed bracket\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid YAML"):
        Settings.load(config_path=cfg)


def test_invalid_yaml_not_a_dict(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML mapping"):
        Settings.load(config_path=cfg)


def test_nested_section_not_a_mapping(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization: just-a-string\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="'summarization' must be a mapping"):
        Settings.load(config_path=cfg)


# ── Value validation ────────────────────────────────────────────────────────────


def test_invalid_summarization_provider(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  model:\n    provider: grok\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="summarization.model.provider"):
        Settings.load(config_path=cfg)


def test_invalid_summarization_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_PROVIDER", "bad-provider")
    with pytest.raises(ConfigError, match="summarization.model.provider"):
        Settings.load(config_path=Path("nonexistent.yaml"))


def test_xai_summarization_provider_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MODEL_PROVIDER", "xai")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.model.provider == "xai"


def test_invalid_transcription_provider(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("transcription:\n  model:\n    provider: whisper-cpp\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="transcription.model.provider"):
        Settings.load(config_path=cfg)


def test_invalid_summary_mode(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  mode: ultra\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="summarization.mode"):
        Settings.load(config_path=cfg)


def test_invalid_max_transcript_chars_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  max_transcript_chars: abc\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="max_transcript_chars"):
        Settings.load(config_path=cfg)


def test_invalid_max_transcript_chars_zero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  max_transcript_chars: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="max_transcript_chars"):
        Settings.load(config_path=cfg)


def test_invalid_max_transcript_chars_negative_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_MAX_TRANSCRIPT_CHARS", "-500")
    with pytest.raises(ConfigError, match="max_transcript_chars"):
        Settings.load(config_path=Path("nonexistent.yaml"))


def test_invalid_timeout_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  timeout_seconds: abc\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="timeout_seconds"):
        Settings.load(config_path=cfg)


def test_invalid_timeout_zero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  timeout_seconds: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="timeout_seconds"):
        Settings.load(config_path=cfg)


def test_invalid_retries_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  retries: abc\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="retries"):
        Settings.load(config_path=cfg)


def test_invalid_retries_negative(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  retries: -1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="retries"):
        Settings.load(config_path=cfg)


def test_invalid_whisper_device(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("transcription:\n  model:\n    device: gpu\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="transcription.model.device"):
        Settings.load(config_path=cfg)


def test_invalid_whisper_compute_type(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("transcription:\n  model:\n    compute_type: bfloat16\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="transcription.model.compute_type"):
        Settings.load(config_path=cfg)


def test_invalid_beam_size_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("transcription:\n  model:\n    beam_size: fast\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="beam_size"):
        Settings.load(config_path=cfg)


def test_invalid_beam_size_zero_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_TRANSCRIPTION_MODEL_BEAM_SIZE", "0")
    with pytest.raises(ConfigError, match="beam_size"):
        Settings.load(config_path=Path("nonexistent.yaml"))


def test_invalid_chunking_mode(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  chunking_mode: stream\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="chunking_mode"):
        Settings.load(config_path=cfg)


def test_chunking_mode_truncate_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_CHUNKING_MODE", "truncate")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.summarization.chunking_mode == "truncate"


def test_summary_language_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  language: ru\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert s.summarization.language == "ru"


def test_invalid_summary_language(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("summarization:\n  language: en\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="summarization.language"):
        Settings.load(config_path=cfg)


def test_invalid_summary_language_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_SUMMARIZATION_LANGUAGE", "fr")
    with pytest.raises(ConfigError, match="summarization.language"):
        Settings.load(config_path=Path("nonexistent.yaml"))


# ── Preprocessing: defaults ──────────────────────────────────────────────────


def test_preprocessing_defaults() -> None:
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert isinstance(s.preprocessing, PreprocessingSettings)
    assert s.preprocessing.enabled is False
    assert s.preprocessing.sample_rate == 16000
    assert s.preprocessing.channels == 1
    assert s.preprocessing.codec == "pcm_s16le"
    assert s.preprocessing.loudness_normalization is False
    assert s.preprocessing.highpass_hz is None
    assert s.preprocessing.keep_temp is False


# ── Preprocessing: YAML loading ──────────────────────────────────────────────


def test_preprocessing_yaml_loads(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "preprocessing:\n"
        "  enabled: true\n"
        "  sample_rate: 22050\n"
        "  channels: 1\n"
        "  loudness_normalization: true\n"
        "  highpass_hz: 70\n",
        encoding="utf-8",
    )
    s = Settings.load(config_path=cfg)
    assert s.preprocessing.enabled is True
    assert s.preprocessing.sample_rate == 22050
    assert s.preprocessing.channels == 1
    assert s.preprocessing.loudness_normalization is True
    assert s.preprocessing.highpass_hz == 70


def test_preprocessing_minimal_enabled(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  enabled: true\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert s.preprocessing.enabled is True
    assert s.preprocessing.sample_rate == 16000


def test_preprocessing_highpass_null_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  highpass_hz: null\n", encoding="utf-8")
    s = Settings.load(config_path=cfg)
    assert s.preprocessing.highpass_hz is None


# ── Preprocessing: env overrides ─────────────────────────────────────────────


def test_preprocessing_env_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_PREPROCESSING_ENABLED", "true")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.preprocessing.enabled is True


def test_preprocessing_env_sample_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECAP_PREPROCESSING_SAMPLE_RATE", "16000")
    s = Settings.load(config_path=Path("nonexistent.yaml"))
    assert s.preprocessing.sample_rate == 16000


# ── Preprocessing: unknown key ───────────────────────────────────────────────


def test_preprocessing_unknown_key_fails(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  bogus: true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="preprocessing.bogus"):
        Settings.load(config_path=cfg)


# ── Preprocessing: invalid values ────────────────────────────────────────────


def test_preprocessing_invalid_sample_rate_zero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  sample_rate: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="sample_rate"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_channels_zero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  channels: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="channels"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_channels_three(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  channels: 3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="channels"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_codec(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  codec: mp3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="codec"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_highpass_negative(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  highpass_hz: -1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="highpass_hz"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_target_lufs_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  target_lufs: loud\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="target_lufs"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_true_peak_db_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  true_peak_db: peak\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="true_peak_db"):
        Settings.load(config_path=cfg)


def test_preprocessing_invalid_loudness_range_not_a_number(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("preprocessing:\n  loudness_range: wide\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="loudness_range"):
        Settings.load(config_path=cfg)
