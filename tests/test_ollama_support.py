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


class _StallingResp(_FakeResp):
    """Response whose stream goes silent: it yields ``lines``, then the read times out."""

    def __iter__(self):  # noqa: ANN204
        yield from self._lines
        raise TimeoutError("timed out")


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


def test_pull_model_uses_bounded_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The streaming pull must never open the socket with ``timeout=None`` (blocks forever)."""
    seen: list[object] = []

    def record(base_url: str, path: str, body: dict, timeout: object) -> _FakeResp:
        seen.append(timeout)
        return _FakeResp([b'{"status":"success"}\n'])

    monkeypatch.setattr(ollama_support, "_post", record)
    ollama_support.pull_model("http://localhost:11434/v1", "qwen2.5")
    assert seen == [ollama_support.PULL_IDLE_TIMEOUT]
    assert isinstance(ollama_support.PULL_IDLE_TIMEOUT, float)


def test_pull_model_raises_on_stalled_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """A silent socket surfaces as a timeout error instead of hanging (the bridge maps it to failed)."""
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _StallingResp([b'{"status":"downloading"}\n']))
    seen: list[tuple[int, int, str]] = []
    with pytest.raises(TimeoutError):
        ollama_support.pull_model("http://localhost:11434/v1", "x", on_progress=lambda c, t, s: seen.append((c, t, s)))
    assert seen == [(0, 0, "downloading")]  # progress up to the stall was still reported


def test_pull_model_stalled_stream_honours_pending_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancel requested mid-stream wins over the stall: waiting is bounded, not endless."""
    monkeypatch.setattr(ollama_support, "_post", lambda *a, **k: _StallingResp([b'{"status":"downloading"}\n']))
    requested = False

    def on_progress(completed: int, total: int, status: str) -> None:
        nonlocal requested  # the user hits "Отменить" after the first progress line
        requested = True

    with pytest.raises(ollama_support.PullCancelled):
        ollama_support.pull_model("http://localhost:11434/v1", "x", on_progress, lambda: requested)


def test_pull_model_cancel_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """An already-set cancel is honoured before any network call."""

    def fail(*a: object, **k: object) -> None:
        raise AssertionError("network must not be touched after cancel")

    monkeypatch.setattr(ollama_support, "_post", fail)
    with pytest.raises(ollama_support.PullCancelled):
        ollama_support.pull_model("http://localhost:11434/v1", "x", cancel=lambda: True)
