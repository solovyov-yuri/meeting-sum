from __future__ import annotations

import json
from pathlib import Path

import pytest

import desktop_bridge
import secrets_store
from config import ConfigError
from transcript import Segment, Transcript


class FakeTranscriber:
    def transcribe(self, audio: Path, language: str = "ru") -> Transcript:
        return Transcript(segments=(Segment(0.0, 1.0, "обсудили план"),))


class FakeSummarizer:
    def summarize(self, text: str) -> str:
        return "краткое резюме"


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "appdata"
    monkeypatch.setenv("RECAP_DESKTOP_DATA_DIR", str(d))
    # Keychain is never touched in tests.
    monkeypatch.setattr(secrets_store, "has_api_key", lambda provider: False)
    monkeypatch.setattr(secrets_store, "get_api_key", lambda provider: None)
    return d


@pytest.fixture()
def patch_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )


# ── settings ──────────────────────────────────────────────────────────────────


def test_get_settings_shape_and_no_secret() -> None:
    s = desktop_bridge.get_settings()
    assert s["summarization"]["model"]["api_key_configured"] is False
    assert "api_key" not in s["summarization"]["model"]
    assert s["transcription"]["model"]["provider"] == "faster-whisper"


def test_get_settings_degrades_when_keychain_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_provider: str) -> bool:
        raise secrets_store.KeychainError("keyring missing")

    monkeypatch.setattr(secrets_store, "has_api_key", boom)
    # Startup settings load must not hard-fail; masked state degrades to "not saved".
    s = desktop_bridge.get_settings()
    assert s["summarization"]["model"]["api_key_configured"] is False


def test_save_settings_persists_and_strips_secret(data_dir: Path) -> None:
    payload = desktop_bridge.get_settings()
    payload["summarization"]["mode"] = "brief"
    payload["summarization"]["model"]["api_key"] = "sk-should-not-persist"

    assert desktop_bridge.save_settings(payload) == {"ok": True}

    cfg = (data_dir / "config.yaml").read_text(encoding="utf-8")
    assert "sk-should-not-persist" not in cfg
    assert desktop_bridge.get_settings()["summarization"]["mode"] == "brief"


def test_save_settings_rejects_unknown_key() -> None:
    payload = desktop_bridge.get_settings()
    payload["bogus_key"] = 1
    with pytest.raises(ConfigError):
        desktop_bridge.save_settings(payload)


# ── api keys ──────────────────────────────────────────────────────────────────


def test_set_and_delete_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(secrets_store, "set_api_key", lambda p, k: calls.append(("set", p, k)))
    monkeypatch.setattr(secrets_store, "delete_api_key", lambda p: calls.append(("del", p)))

    assert desktop_bridge.set_api_key("openai", "sk-x") == {"ok": True}
    assert desktop_bridge.delete_api_key("openai") == {"ok": True}
    assert calls == [("set", "openai", "sk-x"), ("del", "openai")]


def test_set_api_key_unknown_provider() -> None:
    with pytest.raises(ValueError):
        desktop_bridge.set_api_key("grok", "x")


# ── export ────────────────────────────────────────────────────────────────────


def test_export_summary_writes_requested_formats(tmp_path: Path) -> None:
    out = tmp_path / "out"
    res = desktop_bridge.export_summary(
        {
            "summary_text": "## Тема\n1. пункт",
            "formats": ["telegram", "plain", "json"],
            "target_dir": str(out),
            "base_name": "meeting",
            "mode": "medium",
        }
    )
    assert Path(res["telegram_path"]).exists()
    assert Path(res["plain_path"]).exists()
    assert Path(res["json_path"]).exists()
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert data["mode"] == "medium"


def test_export_summary_subset_formats(tmp_path: Path) -> None:
    res = desktop_bridge.export_summary(
        {"summary_text": "x", "formats": ["json"], "target_dir": str(tmp_path), "base_name": "m"}
    )
    assert res["json_path"] is not None
    assert res["telegram_path"] is None
    assert res["plain_path"] is None


# ── run_recap + history ─────────────────────────────────────────────────────────


def test_run_recap_success_writes_history(tmp_path: Path, patch_factory: None, data_dir: Path) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)

    events: list = []
    payload = {
        "audio_path": str(audio),
        "transcript_path": str(tmp_path / "tr.txt"),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "ollama", "mode": "medium"},
    }
    result = desktop_bridge.run_recap(payload, emit=events.append)

    assert result.status == "success"
    assert (tmp_path / "tr.txt").exists()

    history = desktop_bridge.get_history()["items"]
    assert len(history) == 1
    entry = history[0]
    assert entry["status"] == "success"
    assert entry["audio_name"] == "meeting.wav"
    assert entry["provider"] == "ollama"
    # History stores references only — never the transcript / summary body.
    assert "transcript_text" not in entry
    assert "summary_text" not in entry


def test_streaming_cancel_flag_records_cancelled_history(
    tmp_path: Path, patch_factory: None, data_dir: Path
) -> None:
    # ARCH-002: a pre-existing cancel flag makes the run stop cooperatively and still land
    # in history as `cancelled` (instead of being killed and vanishing).
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)
    flag = tmp_path / "cancel.flag"
    flag.write_text("x", encoding="utf-8")

    payload = {
        "audio_path": str(audio),
        "transcript_path": str(tmp_path / "tr.txt"),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "ollama", "mode": "medium"},
        "cancel_flag": str(flag),
    }
    rc = desktop_bridge._streaming("run_recap", payload)

    assert rc == 0
    history = desktop_bridge.get_history()["items"]
    assert len(history) == 1
    assert history[0]["status"] == "cancelled"


def test_resummarize_reuses_transcript_and_writes_history(
    tmp_path: Path, patch_factory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # make_transcriber must never be called during resummarize.
    import providers.factory as factory_mod

    def boom(_settings: object) -> object:
        raise AssertionError("transcriber must not be built during resummarize")

    monkeypatch.setattr(factory_mod, "make_transcriber", boom)

    transcript_path = tmp_path / "tr.txt"
    transcript_path.write_text("[0.00s -> 1.00s] сохранённый текст\n", encoding="utf-8")

    events: list = []
    payload = {
        "audio_path": str(tmp_path / "meeting.wav"),
        "transcript_path": str(transcript_path),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "ollama", "mode": "medium"},
    }
    result = desktop_bridge.resummarize(payload, emit=events.append)

    assert result.status == "success"
    assert (tmp_path / "sum.txt").exists()
    history = desktop_bridge.get_history()["items"]
    assert len(history) == 1
    assert history[0]["status"] == "success"


def test_run_recap_external_provider_warns(tmp_path: Path, patch_factory: None) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)

    events: list = []
    payload = {
        "audio_path": str(audio),
        "transcript_path": str(tmp_path / "tr.txt"),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "openai"},
    }
    desktop_bridge.run_recap(payload, emit=events.append)
    assert any(e.status == "warning" and "внешн" in e.message.lower() for e in events)


def test_delete_history_item(tmp_path: Path, patch_factory: None) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)
    payload = {
        "audio_path": str(audio),
        "transcript_path": str(tmp_path / "tr.txt"),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "ollama"},
    }
    desktop_bridge.run_recap(payload)
    item_id = desktop_bridge.get_history()["items"][0]["id"]

    assert desktop_bridge.delete_history_item(item_id) == {"ok": True}
    assert desktop_bridge.get_history()["items"] == []


def test_get_history_empty_when_no_file() -> None:
    assert desktop_bridge.get_history() == {"items": []}


# ── test_connection / read_text ─────────────────────────────────────────────────


def test_test_connection_local_provider_ok() -> None:
    res = desktop_bridge.test_connection("ollama")
    assert res["ok"] is True


def test_test_connection_external_without_key() -> None:
    res = desktop_bridge.test_connection("openai")
    assert res["ok"] is False
    assert "ключ" in res["message"].lower()


def test_test_connection_unknown_provider() -> None:
    res = desktop_bridge.test_connection("grok")
    assert res["ok"] is False


def test_read_text_missing(tmp_path: Path) -> None:
    res = desktop_bridge.read_text(str(tmp_path / "nope.txt"))
    assert res == {"text": None, "exists": False}


def test_read_text_existing(tmp_path: Path) -> None:
    f = tmp_path / "t.txt"
    f.write_text("привет", encoding="utf-8")
    res = desktop_bridge.read_text(str(f))
    assert res["exists"] is True
    assert res["text"] == "привет"


def test_read_text_none() -> None:
    assert desktop_bridge.read_text(None) == {"text": None, "exists": False}
