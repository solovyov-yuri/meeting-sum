"""Ollama model presence check + on-demand pull (for the desktop "model not installed" flow).

Cloud providers (openai/xai) have nothing to pull; lm-studio/vllm load models their own way. Only
Ollama exposes a pull API, so this is Ollama-specific. The OpenAI-compatible base URL ends in
``/v1``; the native endpoints (``/api/show``, ``/api/pull``) live at the root. Pure stdlib.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

ProgressCallback = Callable[[int, int, str], None]  # (completed_bytes, total_bytes, status)
CancelCheck = Callable[[], bool]

#: Socket timeout for the streaming pull: it caps connecting and each individual read, and every
#: read that returns data resets it. It is deliberately *not* a cap on the total pull duration —
#: a multi-gigabyte download may run for hours as long as bytes keep arriving. It only bounds how
#: long we wait on a silent socket (stalled registry, half-open TCP, machine sleep), which is also
#: the worst-case latency of a cancel while nothing is arriving. Ollama emits status lines
#: continuously while downloading, but can stay quiet during digest verification of a big model,
#: so keep this generous.
PULL_IDLE_TIMEOUT = 300.0


class PullCancelled(Exception):
    """Raised when an in-progress model pull is cancelled by the user."""


def _native_base(base_url: str) -> str:
    """Strip the OpenAI-compat ``/v1`` suffix to reach Ollama's native API root."""
    return base_url.rstrip("/").removesuffix("/v1")


def _post(base_url: str, path: str, body: dict, timeout: float) -> Any:
    url = f"{_native_base(base_url)}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - caller-configured local Ollama host


def model_installed(base_url: str, model: str) -> bool:
    """True if ``model`` is present in the local Ollama (``/api/show`` → 200, missing → 404)."""
    try:
        with _post(base_url, "/api/show", {"name": model}, timeout=10):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def _iter_lines(resp: Any, cancel: CancelCheck | None) -> Iterator[bytes]:
    """Iterate the streamed response lines, turning a stalled read into a cancel when one is pending.

    A socket timeout is terminal for the connection (the reader refuses further reads), so the read
    cannot be retried after polling ``cancel`` — the poll happens once, on the way out.
    """
    lines = iter(resp)
    while True:
        try:
            line = next(lines)
        except StopIteration:
            return
        except TimeoutError as exc:
            if cancel and cancel():
                raise PullCancelled from exc
            raise
        yield line


def pull_model(
    base_url: str,
    model: str,
    on_progress: ProgressCallback | None = None,
    cancel: CancelCheck | None = None,
) -> None:
    """Pull ``model`` via Ollama's streaming ``/api/pull``, reporting per-layer byte progress.

    Polls ``cancel`` between lines and raises ``PullCancelled`` if set. A silent socket can only
    block for ``PULL_IDLE_TIMEOUT`` (see there): the read then fails, and a pending cancel is
    honoured as ``PullCancelled`` while anything else propagates to the caller's error boundary.
    Note: Ollama keeps pulling server-side after the client disconnects, so a cancelled pull may
    still finish (and be cached).
    """
    if cancel and cancel():  # honour an immediate cancel before touching the network
        raise PullCancelled
    resp = _post(base_url, "/api/pull", {"name": model, "stream": True}, timeout=PULL_IDLE_TIMEOUT)
    with resp:
        for raw in _iter_lines(resp, cancel):
            if cancel and cancel():
                raise PullCancelled
            line = raw.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            status = str(data.get("status") or "")
            total = int(data.get("total") or 0)
            completed = int(data.get("completed") or 0)
            if on_progress:
                on_progress(completed, total, status)
