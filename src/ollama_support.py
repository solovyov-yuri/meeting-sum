"""Ollama model presence check + on-demand pull (for the desktop "model not installed" flow).

Cloud providers (openai/xai) have nothing to pull; lm-studio/vllm load models their own way. Only
Ollama exposes a pull API, so this is Ollama-specific. The OpenAI-compatible base URL ends in
``/v1``; the native endpoints (``/api/show``, ``/api/pull``) live at the root. Pure stdlib.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[int, int, str], None]  # (completed_bytes, total_bytes, status)
CancelCheck = Callable[[], bool]


class PullCancelled(Exception):
    """Raised when an in-progress model pull is cancelled by the user."""


def _native_base(base_url: str) -> str:
    """Strip the OpenAI-compat ``/v1`` suffix to reach Ollama's native API root."""
    return base_url.rstrip("/").removesuffix("/v1")


def _post(base_url: str, path: str, body: dict, timeout: float | None) -> Any:
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


def pull_model(
    base_url: str,
    model: str,
    on_progress: ProgressCallback | None = None,
    cancel: CancelCheck | None = None,
) -> None:
    """Pull ``model`` via Ollama's streaming ``/api/pull``, reporting per-layer byte progress.

    Polls ``cancel`` between lines and raises ``PullCancelled`` if set. Note: Ollama keeps pulling
    server-side after the client disconnects, so a cancelled pull may still finish (and be cached).
    """
    resp = _post(base_url, "/api/pull", {"name": model, "stream": True}, timeout=None)
    with resp:
        for raw in resp:
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
