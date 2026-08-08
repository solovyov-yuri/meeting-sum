from __future__ import annotations

from pathlib import Path

import pytest

from utils import write_text_atomic


def test_creates_file(tmp_path: Path) -> None:
    dest = tmp_path / "out.txt"
    write_text_atomic(dest, "hello")
    assert dest.read_text(encoding="utf-8") == "hello"


def test_overwrites_existing(tmp_path: Path) -> None:
    dest = tmp_path / "out.txt"
    dest.write_text("old", encoding="utf-8")
    write_text_atomic(dest, "new")
    assert dest.read_text(encoding="utf-8") == "new"


def test_no_tmp_file_after_success(tmp_path: Path) -> None:
    dest = tmp_path / "out.txt"
    write_text_atomic(dest, "hello")
    assert not dest.with_suffix(dest.suffix + ".tmp").exists()


def test_old_file_preserved_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "out.txt"
    dest.write_text("old content", encoding="utf-8")

    original_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if target == dest:
            raise OSError("simulated rename failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated"):
        write_text_atomic(dest, "new content")

    assert dest.read_text(encoding="utf-8") == "old content"
    assert not list(tmp_path.glob(f".{dest.name}.*.tmp"))


def test_no_tmp_file_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    dest = tmp_path / "out.txt"
    real_named_temp_file = tempfile.NamedTemporaryFile

    class FailingWriteFile:
        def __init__(self, real: object) -> None:
            self._real = real
            self.name = real.name  # type: ignore[attr-defined]

        def write(self, s: str) -> int:
            raise OSError("simulated write failure")

        def __enter__(self) -> FailingWriteFile:
            self._real.__enter__()  # type: ignore[attr-defined]
            return self

        def __exit__(self, *args: object) -> object:
            return self._real.__exit__(*args)  # type: ignore[attr-defined]

    def fake_named_temp_file(*args: object, **kwargs: object) -> FailingWriteFile:
        return FailingWriteFile(real_named_temp_file(*args, **kwargs))  # type: ignore[arg-type]

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fake_named_temp_file)

    with pytest.raises(OSError, match="simulated"):
        write_text_atomic(dest, "new content")

    assert not dest.exists()
    assert not list(tmp_path.glob(f".{dest.name}.*.tmp"))
