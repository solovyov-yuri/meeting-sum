"""JSON schema for the LLM's structured summary + validation into a MeetingSummary.

The LLM still emits a *rich* JSON (intro / sections / points / actions / joke) — that shape guides
generation. ``parse_summary_json`` validates it and maps it onto the generic ``Block``/``Group``
model with the standard starter labels, so the result is fully editable afterwards. The parser is
tolerant on shape (missing keys default) but strict on type (malformed → ``SummaryValidationError``,
so the caller can fall back to the text path).

This module is the only way a string enters the model from outside a line-based parser, so it is
also where strings are normalised to a single line (see ``_one_line``).
"""

from __future__ import annotations

import json
import re

from formatters import (
    ACTIONS_LABEL,
    INTRO_HEADING,
    JOKE_HEADING,
    PARTICIPANTS_LABEL,
    TAKEAWAYS_LABEL,
    TOPIC_PREFIX,
    points_label,
)
from models import Block, Group, MeetingSummary


class SummaryValidationError(ValueError):
    """The LLM output was not valid JSON, or did not match the expected structure."""


# JSON Schema for OpenAI-compatible ``response_format={"type": "json_schema", ...}``.
SUMMARY_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "intro": {"type": ["string", "null"]},
        "participants": {"type": "array", "items": {"type": "string"}},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": ["string", "null"]},
                    "points": {"type": "array", "items": {"type": "string"}},
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "owner": {"type": ["string", "null"]},
                                "due": {"type": ["string", "null"]},
                            },
                            "required": ["text"],
                        },
                    },
                },
            },
        },
        "takeaways": {"type": "array", "items": {"type": "string"}},
        "joke": {"type": ["string", "null"]},
    },
}


def _strip_wrappers(text: str) -> str:
    """Remove ``<think>`` blocks and a ``` ```json ... ``` ``` code fence if the model added one."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text


_LINE_BREAK_RE = re.compile(r"\s*[\r\n]+\s*")


def _one_line(value: str) -> str:
    """Collapse embedded line breaks into a single space.

    Every renderer is line-based (one heading, one paragraph, one ``- ``/``• `` item per line), and
    the parsers read the text back line by line — so a newline inside a string would come back as a
    *different* block on the next save/export. Normalising here keeps every string in the model
    single-line by construction, which is what makes the render/parse round-trip exact.
    """
    return _LINE_BREAK_RE.sub(" ", value).strip()


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SummaryValidationError(f"Ожидалась строка, получено {type(value).__name__}")
    return _one_line(value) or None


def _str_list(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SummaryValidationError(f"Ожидался список в поле {where}")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SummaryValidationError(f"Ожидалась строка в {where}")
        cleaned = _one_line(item)
        if cleaned:
            out.append(cleaned)
    return tuple(out)


def _action_text(raw: object) -> str | None:
    """One action → a single display string ('text — owner — due'); owner/due fold into the text."""
    if isinstance(raw, str):
        return _clean_str(raw)
    if not isinstance(raw, dict):
        raise SummaryValidationError("Элемент actions должен быть объектом или строкой")
    text = _clean_str(raw.get("text"))
    if not text:
        return None
    tail = " — ".join(x for x in (_clean_str(raw.get("owner")), _clean_str(raw.get("due"))) if x)
    return f"{text} — {tail}" if tail else text


def _section_block(raw: object, mode: str) -> Block:
    if not isinstance(raw, dict):
        raise SummaryValidationError("Элемент sections должен быть объектом")
    title = _clean_str(raw.get("title"))
    groups: list[Group] = []
    points = _str_list(raw.get("points"), "sections[].points")
    if points:
        groups.append(Group(label=points_label(mode), items=points))
    actions_raw = raw.get("actions") or []
    if not isinstance(actions_raw, list):
        raise SummaryValidationError("Поле actions должно быть списком")
    actions = tuple(a for a in (_action_text(x) for x in actions_raw) if a is not None)
    if actions:
        groups.append(Group(label=ACTIONS_LABEL, items=actions))
    heading = f"{TOPIC_PREFIX}{title}" if title else None
    return Block(heading=heading, groups=tuple(groups))


def parse_summary_json(raw: str, mode: str) -> MeetingSummary:
    """Validate the LLM's rich JSON and map it onto blocks. Raises SummaryValidationError."""
    try:
        data = json.loads(_strip_wrappers(raw))
    except json.JSONDecodeError as exc:
        raise SummaryValidationError(f"Невалидный JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SummaryValidationError("Ожидался JSON-объект на верхнем уровне")

    blocks: list[Block] = []
    participants = _str_list(data.get("participants"), "participants")
    if participants:
        blocks.append(Block(heading=PARTICIPANTS_LABEL, groups=(Group(items=participants),)))
    intro = _clean_str(data.get("intro"))
    if intro:
        blocks.append(Block(heading=INTRO_HEADING, paragraphs=(intro,)))

    sections_raw = data.get("sections") or []
    if not isinstance(sections_raw, list):
        raise SummaryValidationError("Поле sections должно быть списком")
    blocks.extend(_section_block(s, mode) for s in sections_raw)

    takeaways = _str_list(data.get("takeaways"), "takeaways")
    if takeaways:
        blocks.append(Block(heading=TAKEAWAYS_LABEL, groups=(Group(items=takeaways),)))
    joke = _clean_str(data.get("joke"))
    if joke:
        blocks.append(Block(heading=JOKE_HEADING, paragraphs=(joke,)))

    if not blocks:
        raise SummaryValidationError("Пустое саммари: нет ни intro, ни секций")
    return MeetingSummary(mode=mode, blocks=tuple(blocks))


def load_summary_json(raw: str) -> MeetingSummary:
    """Deserialize our own ``to_json`` output (``{mode, blocks}``) back into a MeetingSummary.

    Inverse of ``formatters.to_json`` — used by export. Returns an *empty* summary (no blocks) for
    any JSON lacking a ``blocks`` array (e.g. an old ``{mode, intro, sections}`` file), which signals
    the caller to fall back to re-parsing the reopened Markdown."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SummaryValidationError(f"Невалидный JSON: {exc}") from exc
    mode = (isinstance(data, dict) and data.get("mode")) or "medium"
    blocks_raw = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks_raw, list):
        return MeetingSummary(mode=mode, blocks=())
    blocks: list[Block] = []
    for b in blocks_raw:
        if not isinstance(b, dict):
            raise SummaryValidationError("Элемент blocks должен быть объектом")
        groups_raw = b.get("groups") or []
        if not isinstance(groups_raw, list):
            raise SummaryValidationError("Поле groups должно быть списком")
        groups = tuple(
            Group(label=_clean_str(g.get("label")), items=_str_list(g.get("items"), "groups[].items"))
            for g in groups_raw
            if isinstance(g, dict)
        )
        blocks.append(
            Block(
                heading=_clean_str(b.get("heading")),
                paragraphs=_str_list(b.get("paragraphs"), "blocks[].paragraphs"),
                groups=groups,
            )
        )
    return MeetingSummary(mode=mode, blocks=tuple(blocks))
