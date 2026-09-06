"""Native Ollama streaming transport and conservative, tokenizer-free input budgeting."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class GenerationIncomplete(ValueError):
    """A response must not be accepted as a complete summary."""


class SummarizationCancelled(Exception):
    """Cooperative stop, handled by the workflow boundary."""


def estimate_tokens(text: str) -> int:
    """Conservative estimate for prose (including Russian), NOT an exact tokenizer.

    One token per three UTF-8 bytes leaves substantial headroom on the supported
    Russian meeting transcripts. Request budgeting also reserves template overhead.
    """
    return (len(text.encode("utf-8")) + 2) // 3


def chat(
    client,
    *,
    model: str,
    messages: list[dict[str, str]],
    num_ctx: int,
    num_predict: int,
    response_format: dict | None,
    console,
    cancelled: Callable[[], bool],
) -> str:
    body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        "truncate": False,
        "shift": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0},
    }
    if response_format:
        body["format"] = (
            response_format["json_schema"]["schema"] if response_format["type"] == "json_schema" else "json"
        )
    parts: list[str] = []
    complete = False
    with client.stream("POST", "api/chat", json=body) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if cancelled():
                raise SummarizationCancelled()
            if not line:
                continue
            event = json.loads(line)
            if event.get("error"):
                # Do not echo server messages: a proxy may include the request body.
                raise GenerationIncomplete("Ollama сообщила об ошибке генерации.")
            content = event.get("message", {}).get("content", "")
            if content:
                parts.append(content)
                console.print(content, end="", highlight=False, markup=False)
            if event.get("done"):
                if event.get("done_reason") == "length":
                    raise GenerationIncomplete("Ollama исчерпала лимит ответа; неполное саммари не сохранено.")
                complete = True
                logger.info(
                    "Ollama usage: input=%s output=%s context=%d",
                    event.get("prompt_eval_count"),
                    event.get("eval_count"),
                    num_ctx,
                )
                break
    console.print()
    result = "".join(parts).strip()
    if not complete or not result:
        raise GenerationIncomplete("Ollama вернула пустой или незавершённый ответ.")
    return result
