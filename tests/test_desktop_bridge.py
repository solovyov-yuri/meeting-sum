from __future__ import annotations

import json
from pathlib import Path

import pytest

import desktop_bridge
import secrets_store
from config import ConfigError
from transcript import Segment, Transcript


class FakeTranscriber:
    def transcribe(self, audio: Path, language: str = "ru", *, on_progress: object = None) -> Transcript:
        return Transcript(segments=(Segment(0.0, 1.0, "обсудили план"),))


class FakeSummarizer:
    supports_structured = False

    def summarize(self, text: str, structured: bool = False) -> str:
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
    import contextlib

    import providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "make_transcriber", lambda settings: FakeTranscriber())
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    # Full mode now force-preprocesses; stub ffmpeg so run tests don't touch the fake .wav.
    @contextlib.contextmanager
    def _fake_prepared(audio, cfg):  # type: ignore[no-untyped-def]
        yield audio

    monkeypatch.setattr("preprocessing.prepared_audio", _fake_prepared)


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
    out.mkdir()  # SEC-003: export requires an existing directory
    res = desktop_bridge.export_summary(
        {
            "summary_text": "## Тема\n- пункт",
            "formats": ["markdown", "plain", "html", "json"],
            "target_dir": str(out),
            "base_name": "meeting",
            "mode": "medium",
        }
    )
    assert Path(res["markdown_path"]).exists()
    assert Path(res["plain_path"]).exists()
    assert Path(res["html_path"]).exists()
    assert Path(res["json_path"]).exists()
    assert Path(res["html_path"]).read_text(encoding="utf-8").startswith("<!doctype html>")
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert data["mode"] == "medium"


def test_export_summary_renders_from_base_json(tmp_path: Path) -> None:
    # Export must render from the saved base .json (single source of truth), not the summary_text.
    base_json = tmp_path / "m_summary.json"
    base_json.write_text(
        json.dumps(
            {
                "mode": "medium",
                "blocks": [
                    {"heading": "Тема встречи", "paragraphs": ["Из JSON"], "groups": []},
                    {"heading": "Тема: A", "paragraphs": [], "groups": [{"label": "Ключевые обсуждения", "items": ["п1"]}]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    res = desktop_bridge.export_summary(
        {
            "summary_json_path": str(base_json),
            "summary_text": "ИГНОРИРУЕТСЯ, если есть json",
            "formats": ["markdown", "html"],
            "target_dir": str(tmp_path),
            "base_name": "m",
            "mode": "medium",
        }
    )
    md = Path(res["markdown_path"]).read_text(encoding="utf-8")
    assert "## Тема встречи\nИз JSON" in md
    assert "## Тема: A" in md
    assert "ИГНОРИРУЕТСЯ" not in md
    assert "<h2>Тема: A</h2>" in Path(res["html_path"]).read_text(encoding="utf-8")


def test_export_summary_falls_back_from_old_format_json(tmp_path: Path) -> None:
    # A reopened old-format {mode, summary} base .json deserializes empty → must fall back to
    # summary_text (the reopened Markdown), not export blank files.
    old_json = tmp_path / "m_summary.json"
    old_json.write_text(json.dumps({"mode": "medium", "summary": "старый текст"}), encoding="utf-8")
    res = desktop_bridge.export_summary(
        {
            "summary_json_path": str(old_json),
            "summary_text": "*Тема встречи*\nВосстановлено из markdown",
            "formats": ["markdown"],
            "target_dir": str(tmp_path),
            "base_name": "m",
            "mode": "medium",
        }
    )
    md = Path(res["markdown_path"]).read_text(encoding="utf-8")
    assert "Восстановлено из markdown" in md


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="empty-file"),
        pytest.param('{"mode":"medium","blocks":[{"heading":"A",', id="truncated"),
        pytest.param("не json вовсе", id="not-json"),
        pytest.param('{"mode":"medium","blocks":["строка"]}', id="block-not-object"),
        pytest.param('{"mode":"medium","blocks":[{"heading":"A","paragraphs":[1]}]}', id="wrong-item-type"),
    ],
)
def test_export_summary_falls_back_from_corrupt_json(tmp_path: Path, raw: str) -> None:
    # A .json that is unreadable or fails validation must not sink the whole export: the summary
    # text in the payload is intact, so the export renders from it.
    broken = tmp_path / "m_summary.json"
    broken.write_text(raw, encoding="utf-8")
    res = desktop_bridge.export_summary(
        {
            "summary_json_path": str(broken),
            "summary_text": "*Тема встречи*\nВосстановлено из текста",
            "formats": ["markdown", "html"],
            "target_dir": str(tmp_path),
            "base_name": "m",
            "mode": "medium",
        }
    )
    assert "Восстановлено из текста" in Path(res["markdown_path"]).read_text(encoding="utf-8")
    assert "Восстановлено из текста" in Path(res["html_path"]).read_text(encoding="utf-8")


def test_export_summary_falls_back_from_non_utf8_json(tmp_path: Path) -> None:
    broken = tmp_path / "m_summary.json"
    broken.write_bytes(b'{"mode":"medium","blocks":[{"heading":"\xff\xfe\x00"}]}')
    res = desktop_bridge.export_summary(
        {
            "summary_json_path": str(broken),
            "summary_text": "ТЕМА ВСТРЕЧИ\n\nВосстановлено из текста",
            "formats": ["markdown"],
            "target_dir": str(tmp_path),
            "base_name": "m",
            "mode": "medium",
        }
    )
    assert "Восстановлено из текста" in Path(res["markdown_path"]).read_text(encoding="utf-8")


def test_export_summary_without_any_source_raises(tmp_path: Path) -> None:
    # Corrupt .json *and* no usable text: fail loudly instead of writing four empty files.
    broken = tmp_path / "m_summary.json"
    broken.write_text("{не json", encoding="utf-8")
    with pytest.raises(ValueError, match="Нечего экспортировать"):
        desktop_bridge.export_summary(
            {
                "summary_json_path": str(broken),
                "summary_text": "   ",
                "formats": ["markdown", "json"],
                "target_dir": str(tmp_path),
                "base_name": "m",
                "mode": "medium",
            }
        )
    assert not (tmp_path / "m_summary.md").exists()


def test_export_summary_subset_formats(tmp_path: Path) -> None:
    res = desktop_bridge.export_summary(
        {"summary_text": "x", "formats": ["json"], "target_dir": str(tmp_path), "base_name": "m"}
    )
    assert res["json_path"] is not None
    assert res["markdown_path"] is None
    assert res["plain_path"] is None
    assert res["html_path"] is None


def test_save_summary_overwrites_legacy_markdown_and_json(tmp_path: Path, data_dir: Path) -> None:
    summary_path = tmp_path / "meeting_summary.txt"
    summary_path.write_text("старое", encoding="utf-8")
    desktop_bridge._append_history({"id": "h1", "summary_path": str(summary_path)})
    res = desktop_bridge.save_summary(
        {
            "summary_text": "## Тема встречи\nНовый текст\n\n## Тема: A\n### Решения и задачи\n- сделать",
            "summary_path": str(summary_path),
            "mode": "medium",
        }
    )
    # Entries written before the plain-text switch still hold Markdown — it must still parse.
    assert summary_path.read_text(encoding="utf-8").startswith("## Тема встречи\nНовый текст")
    # JSON sibling is re-derived (structured) from the edited Markdown.
    json_path = Path(res["json_path"])
    assert json_path == tmp_path / "meeting_summary.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["blocks"][0]["heading"] == "Тема встречи"
    assert data["blocks"][0]["paragraphs"] == ["Новый текст"]
    assert data["blocks"][1]["heading"] == "Тема: A"
    assert data["blocks"][1]["groups"][0]["label"] == "Решения и задачи"
    assert data["blocks"][1]["groups"][0]["items"] == ["сделать"]


def test_save_summary_missing_dir_raises(tmp_path: Path, data_dir: Path) -> None:
    summary_path = tmp_path / "nope" / "s_summary.txt"
    desktop_bridge._append_history({"id": "h1", "summary_path": str(summary_path)})
    with pytest.raises(ValueError, match="Каталог не существует"):
        desktop_bridge.save_summary({"summary_text": "x", "summary_path": str(summary_path), "mode": "medium"})


def test_save_summary_outside_history_denied(tmp_path: Path, data_dir: Path) -> None:
    # The save target is scoped to summary files the history points at, so the command cannot be
    # used to write anywhere on disk — including next to a legitimate entry.
    known = tmp_path / "meeting_summary.txt"
    desktop_bridge._append_history({"id": "h1", "summary_path": str(known)})

    victim = tmp_path / "startup" / "evil.bat"
    victim.parent.mkdir()
    with pytest.raises(ValueError, match="не найден в истории"):
        desktop_bridge.save_summary({"summary_text": "x", "summary_path": str(victim), "mode": "medium"})
    assert not victim.exists()

    # …nor via a traversal that normalises to a path outside the allowed set.
    traversal = tmp_path / "sub" / ".." / "startup" / "evil.bat"
    (tmp_path / "sub").mkdir()
    with pytest.raises(ValueError, match="не найден в истории"):
        desktop_bridge.save_summary({"summary_text": "x", "summary_path": str(traversal), "mode": "medium"})
    assert not victim.exists()


def test_save_summary_denied_when_history_only_references_other_keys(tmp_path: Path, data_dir: Path) -> None:
    # Only summary_path is writable: a transcript the history points at must not be overwritable
    # with summary text.
    transcript = tmp_path / "meeting.txt"
    transcript.write_text("исходный транскрипт", encoding="utf-8")
    desktop_bridge._append_history({"id": "h1", "transcript_path": str(transcript)})
    with pytest.raises(ValueError, match="не найден в истории"):
        desktop_bridge.save_summary({"summary_text": "x", "summary_path": str(transcript), "mode": "medium"})
    assert transcript.read_text(encoding="utf-8") == "исходный транскрипт"


@pytest.mark.parametrize(
    "base_name",
    ["../evil", "..\\..\\evil", "sub/evil", "sub\\evil", "..", ".", "", "   ", "C:evil", "name:stream", "a\x00b"],
)
def test_export_summary_rejects_unsafe_base_name(tmp_path: Path, base_name: str) -> None:
    with pytest.raises(ValueError, match="Недопустимое имя файла"):
        desktop_bridge.export_summary(
            {"summary_text": "x", "formats": ["json"], "target_dir": str(tmp_path), "base_name": base_name}
        )
    # Nothing was written anywhere around the target directory.
    assert list(tmp_path.rglob("*evil*")) == []


def test_export_summary_accepts_ordinary_file_names(tmp_path: Path) -> None:
    # Base names come from a real audio file stem: spaces, punctuation and non-ASCII must pass.
    res = desktop_bridge.export_summary(
        {
            "summary_text": "x",
            "formats": ["json"],
            "target_dir": str(tmp_path),
            "base_name": "Созвон (2026-07-05) #1 & co",
        }
    )
    assert Path(res["json_path"]) == tmp_path / "Созвон (2026-07-05) #1 & co_summary.json"
    assert Path(res["json_path"]).exists()


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
    # The desktop's summary .txt (and the text handed to the editor) is the plain Telegram form.
    summary_file = (tmp_path / "sum.txt").read_text(encoding="utf-8")
    assert summary_file == result.summary_text
    assert not summary_file.startswith("#") and "\n#" not in summary_file  # no Markdown headings

    history = desktop_bridge.get_history()["items"]
    assert len(history) == 1
    entry = history[0]
    assert entry["status"] == "success"
    assert entry["audio_name"] == "meeting.wav"
    assert entry["provider"] == "ollama"
    # History stores references only — never the transcript / summary body.
    assert "transcript_text" not in entry
    assert "summary_text" not in entry


def test_save_summary_accepts_the_path_a_run_produced(tmp_path: Path, patch_factory: None, data_dir: Path) -> None:
    # The live flow: the UI edits the summary of a finished run and saves it back to the very path
    # the run reported, which the history entry references.
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)
    result = desktop_bridge.run_recap(
        {
            "audio_path": str(audio),
            "transcript_path": str(tmp_path / "tr.txt"),
            "summary_path": str(tmp_path / "sum.txt"),
            "overrides": {"provider": "ollama", "mode": "medium"},
        }
    )
    assert result.summary_path is not None

    saved = desktop_bridge.save_summary(
        {"summary_text": "ТЕМА ВСТРЕЧИ\n\nОтредактировано.", "summary_path": str(result.summary_path), "mode": "medium"}
    )
    assert Path(saved["summary_path"]).read_text(encoding="utf-8") == "ТЕМА ВСТРЕЧИ\n\nОтредактировано."
    assert Path(saved["json_path"]).exists()


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


def test_streaming_resummarize_cancel_flag_records_cancelled_history(
    tmp_path: Path, patch_factory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The cancel flag must reach resummarize_one too: a stop lands in history as `cancelled`
    # (not `success`), with the existing transcript untouched on disk.
    import providers.factory as factory_mod

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("no provider must be built after cancellation")

    monkeypatch.setattr(factory_mod, "make_transcriber", boom)
    monkeypatch.setattr(factory_mod, "make_summarizer", boom)

    transcript_path = tmp_path / "tr.txt"
    transcript_path.write_text("[0.00s -> 1.00s] сохранённый текст\n", encoding="utf-8")
    flag = tmp_path / "cancel.flag"
    flag.write_text("x", encoding="utf-8")

    payload = {
        "audio_path": str(tmp_path / "meeting.wav"),
        "transcript_path": str(transcript_path),
        "summary_path": str(tmp_path / "sum.txt"),
        "overrides": {"provider": "ollama", "mode": "medium"},
        "cancel_flag": str(flag),
    }
    rc = desktop_bridge._streaming("resummarize", payload)

    assert rc == 0
    history = desktop_bridge.get_history()["items"]
    assert [item["status"] for item in history] == ["cancelled"]
    assert history[0]["transcript_path"] == str(transcript_path)
    assert transcript_path.exists()
    assert not (tmp_path / "sum.txt").exists()


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


def test_serve_reuses_transcriber_across_runs(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PERF-001: the persistent worker builds the Whisper model once and reuses it for a second run.
    import logging

    import providers.factory as factory_mod

    calls = {"n": 0}

    def counting_make_transcriber(settings: object) -> FakeTranscriber:
        calls["n"] += 1
        return FakeTranscriber()

    monkeypatch.setattr(factory_mod, "make_transcriber", counting_make_transcriber)
    monkeypatch.setattr(
        factory_mod,
        "make_summarizer",
        lambda settings, provider, mode, model_override=None, summary_language=None: FakeSummarizer(),
    )

    def make_req(i: int) -> str:
        audio = tmp_path / f"m{i}.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 32)
        return json.dumps(
            {
                "audio_path": str(audio),
                "transcript_path": str(tmp_path / f"tr{i}.txt"),
                "summary_path": str(tmp_path / f"sum{i}.txt"),
                "overrides": {"provider": "ollama", "mode": "medium"},
            }
        )

    saved = logging.getLogger().handlers[:]
    try:
        rc = desktop_bridge.serve([make_req(1), make_req(2)])
    finally:
        root = logging.getLogger()
        root.handlers.clear()
        root.handlers.extend(saved)

    assert rc == 0
    assert calls["n"] == 1  # model built once, reused for the second run
    assert len(desktop_bridge.get_history()["items"]) == 2  # both runs completed + recorded


def test_history_append_delete_under_lock(data_dir: Path) -> None:
    # REL-006: append/delete run under a cross-process file lock; sequential ops must still
    # round-trip correctly (and the lock must be re-acquirable across calls).
    for i in range(3):
        desktop_bridge._append_history({"id": f"e{i}", "status": "success"})
    ids = [it["id"] for it in desktop_bridge.get_history()["items"]]
    assert ids == ["e2", "e1", "e0"]  # newest first

    desktop_bridge.delete_history_item("e1")
    assert [it["id"] for it in desktop_bridge.get_history()["items"]] == ["e2", "e0"]
    # A stale lock file left behind must not break subsequent operations.
    desktop_bridge._append_history({"id": "e3", "status": "success"})
    assert desktop_bridge.get_history()["items"][0]["id"] == "e3"


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


# ── run_mode (transcribe-only / preprocess-only) ────────────────────────────────


def test_run_recap_transcribe_mode_skips_summary(tmp_path: Path, patch_factory: None, data_dir: Path) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)
    payload = {
        "audio_path": str(audio),
        "transcript_path": str(tmp_path / "tr.txt"),
        "summary_path": str(tmp_path / "sum.txt"),
        "run_mode": "transcribe",
        "overrides": {"provider": "ollama"},
    }
    result = desktop_bridge.run_recap(payload, emit=lambda e: None)
    assert result.status == "success"
    assert (tmp_path / "tr.txt").exists()
    assert result.summary_path is None
    assert not (tmp_path / "sum.txt").exists()


def test_run_recap_preprocess_mode(tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 32)
    monkeypatch.setattr("preprocessing.preprocess_audio", lambda inp, out, cfg: out.write_bytes(b"x"))
    result = desktop_bridge.run_recap({"audio_path": str(audio), "run_mode": "preprocess"}, emit=lambda e: None)
    assert result.status == "success"
    assert result.output_path is not None
    assert result.output_path.name == "meeting.preprocessed.wav"
    assert result.output_path.exists()


# ── list_models ─────────────────────────────────────────────────────────────────


def test_list_models_unknown_provider() -> None:
    res = desktop_bridge.list_models("grok")
    assert res["models"] == []
    assert "провайдер" in res["error"].lower()


def test_list_models_external_without_key(data_dir: Path) -> None:
    # openai with no stored key must not attempt a network call — clean error, empty list.
    res = desktop_bridge.list_models("openai")
    assert res["models"] == []
    assert "ключ" in res["error"].lower()


def test_list_models_success_dedupes_and_sorts(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    class _Model:
        def __init__(self, id_: str) -> None:
            self.id = id_

    class _Resp:
        data = [_Model("qwen2.5"), _Model("llama3.1"), _Model("llama3.1")]

    class _Client:
        def __init__(self, **_kw: object) -> None:
            self.models = self

        def list(self) -> _Resp:
            return _Resp()

    monkeypatch.setattr(openai, "OpenAI", _Client)
    res = desktop_bridge.list_models("ollama")  # local provider → no key required
    assert res["error"] is None
    assert res["models"] == ["llama3.1", "qwen2.5"]


def test_list_models_network_error_returns_clean(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    class _Models:
        def list(self) -> object:
            raise ConnectionError("connection refused")

    class _Client:
        def __init__(self, **_kw: object) -> None:
            self.models = _Models()

    monkeypatch.setattr(openai, "OpenAI", _Client)
    res = desktop_bridge.list_models("ollama")
    assert res["models"] == []
    assert res["error"]


def test_test_connection_ignores_saved_base_url_for_other_provider(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CODE-005: saved config is ollama with a local base_url; checking a *different* draft
    # provider (openai) must not borrow ollama's local URL and mis-report "local".
    desktop_bridge.save_settings(
        {"summarization": {"model": {"provider": "ollama", "base_url": "http://localhost:11434/v1"}}}
    )
    monkeypatch.setattr(secrets_store, "has_api_key", lambda provider: False)
    res = desktop_bridge.test_connection("openai")
    assert res["ok"] is False
    assert "ключ" in res["message"].lower()  # treated as external, key missing


def test_get_settings_exposes_per_provider_key_state(monkeypatch: pytest.MonkeyPatch) -> None:
    # CODE-007: key state is exposed for every provider, not only the saved one.
    monkeypatch.setattr(secrets_store, "has_api_key", lambda provider: provider == "xai")
    keys = desktop_bridge.get_settings()["api_keys_configured"]
    assert keys["xai"] is True
    assert keys["openai"] is False


def test_save_settings_ignores_api_keys_configured(data_dir: Path) -> None:
    # CODE-007: the read-only view field must not break the strict save round-trip.
    settings = desktop_bridge.get_settings()
    assert "api_keys_configured" in settings
    desktop_bridge.save_settings(settings)  # must not raise ConfigError


def test_read_text_missing(tmp_path: Path) -> None:
    res = desktop_bridge.read_text(str(tmp_path / "nope.txt"))
    assert res == {"text": None, "exists": False}


def test_read_text_existing(data_dir: Path) -> None:
    # A file under the app data dir is in scope (SEC-003).
    f = desktop_bridge._data_dir() / "t.txt"
    f.write_text("привет", encoding="utf-8")
    res = desktop_bridge.read_text(str(f))
    assert res["exists"] is True
    assert res["text"] == "привет"


def test_read_text_history_referenced_is_in_scope(tmp_path: Path, data_dir: Path) -> None:
    # SEC-003: a file the history points at is readable even outside the data dir.
    f = tmp_path / "summary.txt"
    f.write_text("итог", encoding="utf-8")
    desktop_bridge._append_history({"id": "h1", "summary_path": str(f)})
    res = desktop_bridge.read_text(str(f))
    assert res == {"text": "итог", "exists": True}


def test_read_text_out_of_scope_denied(tmp_path: Path, data_dir: Path) -> None:
    # SEC-003: an existing file that is neither under the data dir nor history-referenced is
    # denied, reported like "missing" (no info leak).
    f = tmp_path / "secret.txt"
    f.write_text("секрет", encoding="utf-8")
    assert desktop_bridge.read_text(str(f)) == {"text": None, "exists": False}


def test_read_text_binary_in_scope_handled(data_dir: Path) -> None:
    # REL side of SEC-003: a non-UTF-8 file in scope fails cleanly, not with a raw traceback.
    f = desktop_bridge._data_dir() / "blob.bin"
    f.write_bytes(b"\xff\xfe\x00\x01")
    res = desktop_bridge.read_text(str(f))
    assert res["exists"] is False
    assert "error" in res


def test_save_summary_round_trips_the_plain_text(tmp_path: Path, data_dir: Path) -> None:
    # The desktop edits the plain text itself: the .txt keeps it verbatim and the .json is
    # re-derived from it, so a reopened item shows the edits and exports reflect them.
    summary_path = tmp_path / "meeting_summary.txt"
    desktop_bridge._append_history({"id": "h1", "summary_path": str(summary_path)})
    plain = "ТЕМА ВСТРЕЧИ\n\nНовый текст.\n\n" + "━" * 20 + "\n\nТЕМА: A\n\nРешения и задачи:\n• Сделать."
    res = desktop_bridge.save_summary({"summary_text": plain, "summary_path": str(summary_path), "mode": "medium"})

    assert summary_path.read_text(encoding="utf-8") == plain
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert data["blocks"][0]["heading"] == "Тема встречи"  # case restored for the other formats
    assert data["blocks"][0]["paragraphs"] == ["Новый текст."]
    assert data["blocks"][1]["heading"] == "Тема: A"
    assert data["blocks"][1]["groups"] == [{"label": "Решения и задачи", "items": ["Сделать."]}]


def test_export_summary_from_edited_plain_text(tmp_path: Path) -> None:
    # No base .json (or an unusable one) → the export parses the edited plain text.
    res = desktop_bridge.export_summary(
        {
            "summary_text": "ТЕМА ВСТРЕЧИ\n\nИз простого текста.\n\nРешения и задачи:\n• Сделать.",
            "formats": ["markdown", "plain"],
            "target_dir": str(tmp_path),
            "base_name": "m",
            "mode": "medium",
        }
    )
    assert "## Тема встречи\nИз простого текста." in Path(res["markdown_path"]).read_text(encoding="utf-8")
    assert "• Сделать." in Path(res["plain_path"]).read_text(encoding="utf-8")


def test_export_summary_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="не существует"):
        desktop_bridge.export_summary(
            {"summary_text": "x", "formats": ["json"], "target_dir": str(tmp_path / "nope"), "base_name": "m"}
        )


def test_configure_logging_writes_file(data_dir: Path) -> None:
    # ARCH-004: bridge logging lands in a rotating file under the data dir.
    import logging

    saved = logging.getLogger().handlers[:]
    try:
        desktop_bridge._configure_logging()
        logging.getLogger("recap.test").error("boom")
        logging.shutdown()
        log_file = desktop_bridge._data_dir() / "logs" / "recap-bridge.log"
        assert log_file.exists()
        assert "boom" in log_file.read_text(encoding="utf-8")
    finally:
        root = logging.getLogger()
        root.handlers.clear()
        root.handlers.extend(saved)


def test_read_text_none() -> None:
    assert desktop_bridge.read_text(None) == {"text": None, "exists": False}
