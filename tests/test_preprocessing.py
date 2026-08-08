from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import PreprocessingSettings
from preprocessing import PreprocessingError, prepared_audio, preprocess_audio


def _settings(**kwargs) -> PreprocessingSettings:
    return PreprocessingSettings(**kwargs)


# ── Disabled ─────────────────────────────────────────────────────────────────


def test_disabled_returns_original_path(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=False)
    with prepared_audio(audio, settings) as result:
        assert result == audio


def test_disabled_does_not_call_subprocess(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=False)
    with patch("subprocess.run") as mock_run:
        with prepared_audio(audio, settings):
            pass
        mock_run.assert_not_called()


# ── Enabled: command structure ────────────────────────────────────────────────


def test_enabled_command_contains_expected_args(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings) as result:
            assert len(captured) == 1
            cmd = captured[0]
            assert cmd[0] == "ffmpeg"
            assert "-i" in cmd
            assert str(audio) in cmd
            assert "-ac" in cmd
            assert "1" in cmd
            assert "-ar" in cmd
            assert "16000" in cmd
            assert "-c:a" in cmd
            assert "pcm_s16le" in cmd
            assert str(result).endswith(".preprocessed.wav")


def test_enabled_no_filters_by_default(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings):
            cmd = captured[0]
            assert "-af" not in cmd


# ── Enabled: filters ─────────────────────────────────────────────────────────


def test_loudness_normalization_adds_loudnorm_filter(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, loudness_normalization=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings):
            cmd = captured[0]
            assert "-af" in cmd
            af_value = cmd[cmd.index("-af") + 1]
            assert "loudnorm" in af_value


def test_highpass_hz_adds_highpass_filter(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, highpass_hz=70)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings):
            cmd = captured[0]
            assert "-af" in cmd
            af_value = cmd[cmd.index("-af") + 1]
            assert "highpass" in af_value
            assert "70" in af_value


def test_both_filters_combined(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, highpass_hz=70, loudness_normalization=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings):
            cmd = captured[0]
            af_value = cmd[cmd.index("-af") + 1]
            assert "highpass" in af_value
            assert "loudnorm" in af_value


# ── Error handling ────────────────────────────────────────────────────────────


def test_ffmpeg_not_found_raises_preprocessing_error(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True)

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise FileNotFoundError("ffmpeg")

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="ffmpeg not found"):
            with prepared_audio(audio, settings):
                pass


def test_ffmpeg_failure_stderr_in_message(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True)

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, cmd, stderr="Invalid data found")

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="Invalid data found"):
            with prepared_audio(audio, settings):
                pass


# ── Temp file lifecycle ───────────────────────────────────────────────────────


def test_temp_file_deleted_after_context_keep_temp_false(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, keep_temp=False)

    tmp_path_captured: list[Path] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings) as result:
            tmp_path_captured.append(result)

    assert not tmp_path_captured[0].exists()


def test_temp_file_kept_after_context_keep_temp_true(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, keep_temp=True)

    tmp_path_captured: list[Path] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with prepared_audio(audio, settings) as result:
            tmp_path_captured.append(result)

    assert tmp_path_captured[0].exists()
    tmp_path_captured[0].unlink()


# ── preprocess_audio: direct function ────────────────────────────────────────


def test_preprocess_audio_output_path_is_last_arg(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        result = preprocess_audio(audio, output, settings)

    assert result == output
    cmd = captured[0]
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd
    assert str(audio) in cmd
    assert cmd[-1] == str(output)


def test_preprocess_audio_uses_nostdin_and_devnull(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    captured: list[list[str]] = []
    captured_kwargs: list[dict[str, object]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        captured_kwargs.append(kwargs)
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, output, settings)

    cmd = captured[0]
    assert "-nostdin" in cmd
    assert captured_kwargs[0]["stdin"] is subprocess.DEVNULL
    assert captured_kwargs[0]["timeout"] is not None


def test_preprocess_audio_timeout_raises_preprocessing_error(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd, timeout=1)

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="timed out"):
            preprocess_audio(audio, output, settings)


def test_preprocess_audio_contains_required_args(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, output, settings)

    cmd = captured[0]
    assert "-ac" in cmd
    assert str(settings.channels) in cmd
    assert "-ar" in cmd
    assert str(settings.sample_rate) in cmd
    assert "-c:a" in cmd
    assert settings.codec in cmd


def test_preprocess_audio_ffmpeg_not_found(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise FileNotFoundError("ffmpeg")

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="ffmpeg not found"):
            preprocess_audio(audio, output, settings)


def test_preprocess_audio_called_process_error_none_stderr(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, cmd, stderr=None)

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="ffmpeg failed"):
            preprocess_audio(audio, output, settings)


def test_preprocess_audio_called_process_error_with_stderr(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings()

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, cmd, stderr="codec not found")

    with patch("subprocess.run", fake_run):
        with pytest.raises(PreprocessingError, match="codec not found"):
            preprocess_audio(audio, output, settings)


def test_preprocess_audio_loudnorm_filter(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings(loudness_normalization=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, output, settings)

    cmd = captured[0]
    assert "-af" in cmd
    assert "loudnorm" in cmd[cmd.index("-af") + 1]


def test_preprocess_audio_highpass_filter(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings(highpass_hz=70)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, output, settings)

    cmd = captured[0]
    assert "-af" in cmd
    af_val = cmd[cmd.index("-af") + 1]
    assert "highpass" in af_val
    assert "70" in af_val


def test_preprocess_audio_both_filters_combined(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    output = tmp_path / "out.wav"
    settings = _settings(highpass_hz=70, loudness_normalization=True)

    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, output, settings)

    af_val = captured[0][captured[0].index("-af") + 1]
    assert "highpass" in af_val
    assert "loudnorm" in af_val


def test_prepared_audio_delegates_to_preprocess_audio(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True)

    calls: list[tuple] = []

    def fake_preprocess(a: Path, o: Path, s: PreprocessingSettings) -> Path:
        calls.append((a, o, s))
        return o

    with patch("preprocessing.preprocess_audio", fake_preprocess):
        with prepared_audio(audio, settings) as result:
            assert len(calls) == 1
            assert calls[0][0] == audio
            assert calls[0][2] is settings
            assert result == calls[0][1]


# ── ffmpeg resolution ────────────────────────────────────────────────────────

_EXE = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _captured_ffmpeg(tmp_path: Path) -> str:
    """Run preprocess_audio with a stubbed subprocess and return the resolved ffmpeg argv[0]."""
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        preprocess_audio(audio, tmp_path / "out.wav", _settings())
    return captured[0][0]


def _fake_app_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, frozen: bool = True
) -> Path:
    """Fake the portable layout: <app>/recap-bridge/recap-bridge.exe. Returns the app dir."""
    app_dir = tmp_path / "app"
    bridge_dir = app_dir / "recap-bridge"
    bridge_dir.mkdir(parents=True)
    exe = bridge_dir / ("recap-bridge.exe" if os.name == "nt" else "recap-bridge")
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(exe))
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.delattr(sys, "frozen", raising=False)
    return app_dir


def test_frozen_uses_ffmpeg_next_to_app_exe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = _fake_app_layout(tmp_path, monkeypatch)
    bundled = app_dir / _EXE
    bundled.write_bytes(b"")
    monkeypatch.setenv("PATH", "")

    assert _captured_ffmpeg(tmp_path) == str(bundled)


def test_frozen_uses_ffmpeg_next_to_the_bridge_exe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = _fake_app_layout(tmp_path, monkeypatch)
    bundled = app_dir / "recap-bridge" / _EXE
    bundled.write_bytes(b"")
    monkeypatch.setenv("PATH", "")

    assert _captured_ffmpeg(tmp_path) == str(bundled)


def test_frozen_without_bundled_ffmpeg_falls_back_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_app_layout(tmp_path, monkeypatch)

    assert _captured_ffmpeg(tmp_path) == "ffmpeg"


def test_not_frozen_always_uses_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = _fake_app_layout(tmp_path, monkeypatch, frozen=False)
    (app_dir / _EXE).write_bytes(b"")

    assert _captured_ffmpeg(tmp_path) == "ffmpeg"


def test_temp_file_deleted_even_on_exception(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 16)
    settings = _settings(enabled=True, keep_temp=False)

    tmp_path_captured: list[Path] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        return MagicMock(returncode=0)

    with patch("subprocess.run", fake_run):
        with pytest.raises(RuntimeError):
            with prepared_audio(audio, settings) as result:
                tmp_path_captured.append(result)
                raise RuntimeError("transcription failed")

    assert not tmp_path_captured[0].exists()
