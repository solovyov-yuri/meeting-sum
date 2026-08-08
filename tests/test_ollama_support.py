import io
import urllib.error

import pytest

import ollama_support


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("http://localhost:11434/v1", "http://localhost:11434"),
        ("http://localhost:11434/v1/", "http://localhost:11434"),
        ("http://host:11434", "http://host:11434"),
    ],
)
def test_native_base(base_url: str, expected: str) -> None:
    assert ollama_support._native_base(base_url) == expected


class _FakeResp:
    """Context-manager + line-iterable stand-in for urlopen's response."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def __iter__(self):  # noqa: ANN204
        return iter(self._lines)


def test_model_installed_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _FakeResp([]))
    assert ollama_support.model_installed("http://localhost:11434/v1", "qwen2.5") is True


def test_model_installed_false_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_404(*a: object, **k: object):  # noqa: ANN202
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO())  # type: ignore[arg-type]

    monkeypatch.setattr(ollama_support, "_post", raise_404)
    assert ollama_support.model_installed("http://localhost:11434/v1", "nope") is False


def test_model_installed_reraises_other_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_500(*a: object, **k: object):  # noqa: ANN202
        raise urllib.error.HTTPError("u", 500, "Server Error", {}, io.BytesIO())  # type: ignore[arg-type]

    monkeypatch.setattr(ollama_support, "_post", raise_500)
    with pytest.raises(urllib.error.HTTPError):
        ollama_support.model_installed("http://localhost:11434/v1", "x")


def test_pull_model_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [
        b'{"status":"pulling manifest"}\n',
        b'{"status":"downloading","total":100,"completed":40}\n',
        b'{"status":"success"}\n',
    ]
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _FakeResp(lines))
    seen: list[tuple[int, int, str]] = []
    ollama_support.pull_model("http://localhost:11434/v1", "qwen2.5", on_progress=lambda c, t, s: seen.append((c, t, s)))
    assert (40, 100, "downloading") in seen


def test_pull_model_raises_on_error_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _FakeResp([b'{"error":"model not found"}\n']))
    with pytest.raises(RuntimeError, match="model not found"):
        ollama_support.pull_model("http://localhost:11434/v1", "x")


def test_pull_model_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _FakeResp([b'{"status":"downloading"}\n']))
    with pytest.raises(ollama_support.PullCancelled):
        ollama_support.pull_model("http://localhost:11434/v1", "x", cancel=lambda: True)
