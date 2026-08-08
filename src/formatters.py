from __future__ import annotations

import json
import re
from html import escape

from models import Block, Group, MeetingSummary

# The single source of truth for every output format is the structured ``MeetingSummary`` — a flat
# list of ``Block`` (free-text heading + prose + labeled ``Group`` sub-lists). It is produced either
# by validating the LLM's rich JSON (``summary_schema.parse_summary_json``, which maps it onto blocks
# with the standard starter labels below) or by parsing an edited summary back (``parse_summary_text``
# → ``parse_plain`` for the desktop's editable plain text, ``parse_summary`` for Markdown).
# All renderers take the object, so the formats share one structure and differ only in formatting:
#   - Markdown  → ``render_markdown``  (export/CLI: ``##`` block, ``###`` group, ``- `` items)
#   - Plain     → ``to_plain``         (Telegram-ready: CAPS headers, ``━`` separators, ``• `` per line)
#   - HTML      → ``to_html``          (``<h2>``/``<h3>``/``<ul>``/``<p>`` + CSS)
#   - JSON      → ``to_json``          (``{mode, blocks:[…]}``)
#
# Headings/labels are free text: whatever a user types survives save→export. The guarantee is render
# idempotence — ``render(parse(render(obj))) == render(obj)`` — not a round-trip of arbitrary Markdown.

_SEP = "━" * 20

# Starter labels used when mapping the LLM's rich JSON onto blocks. After that they are ordinary
# free text a user may rename.
POINTS_LABEL = {"medium": "Ключевые обсуждения", "detailed": "Ход обсуждения"}
ACTIONS_LABEL = "Решения и задачи"
PARTICIPANTS_LABEL = "Участники"
TAKEAWAYS_LABEL = "Главное"
INTRO_HEADING = "Тема встречи"
JOKE_HEADING = "Курьёз встречи"
TOPIC_PREFIX = "Тема: "


def points_label(mode: str) -> str:
    return POINTS_LABEL.get(mode, "Ключевые обсуждения")


# ── Markdown (canonical / editable) ──────────────────────────────────────────


def render_markdown(summary: MeetingSummary) -> str:
    """Render the structured summary to canonical Markdown (## blocks, ### groups, - items)."""
    parts: list[str] = []
    for block in summary.blocks:
        if block.heading and block.paragraphs:
            parts.append(f"## {block.heading}\n" + "\n".join(block.paragraphs))
        elif block.heading:
            parts.append(f"## {block.heading}")
        elif block.paragraphs:
            parts.append("\n".join(block.paragraphs))
        for group in block.groups:
            head = f"### {group.label}\n" if group.label else ""
            parts.append(head + "\n".join(f"- {it}" for it in group.items))
    return "\n\n".join(p for p in parts if p).strip()


# ── Plain text (Meeting Summary.pdf layout) ──────────────────────────────────


def _upper_heading(text: str) -> str:
    """Upper-case a block heading: whole heading, or just the label before a colon."""
    if ":" in text:
        label, rest = text.split(":", 1)
        return f"{label.upper()}:{rest}"
    return text.upper()


def to_plain(summary: MeetingSummary) -> str:
    """Render as Telegram-ready plain text.

    No markup at all (no ``#``/``*``/backticks): upper-case headers, ``━`` rules between top-level
    sections, one ``• `` bullet per line under its label, and a blank line between every heading,
    paragraph, list and section — so a copy-paste into Telegram keeps the layout.
    """
    parts: list[str] = []
    emitted = False
    for block in summary.blocks:
        if block.heading:
            if emitted:
                parts.append(_SEP)
            parts.append(_upper_heading(block.heading))
        # One part, so soft-wrapped prose keeps its line breaks instead of gaining a blank line
        # between every line (``parse_summary`` yields one "paragraph" per source line).
        if block.paragraphs:
            parts.append("\n".join(block.paragraphs))
        for group in block.groups:
            if not group.items:
                continue
            bullets = "\n".join(f"• {it}" for it in group.items)
            label = group.label.strip().rstrip(":").strip() if group.label else None
            parts.append(f"{label}:\n{bullets}" if label else bullets)
        emitted = emitted or bool(block.heading or block.paragraphs or block.groups)
    return "\n\n".join(p for p in parts if p).strip()


# ── HTML ─────────────────────────────────────────────────────────────────────

_HTML_DOC = """\
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Итоги встречи</title>
  <style>
    body {
      margin: 0;
      padding: 24px;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.5;
      color: #1f2937;
      background: #f3f4f6;
    }
    .container {
      max-width: 920px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 16px;
      padding: 28px;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
    }
    section {
      margin-top: 22px;
      padding-top: 18px;
      border-top: 1px solid #e5e7eb;
    }
    section:first-child {
      margin-top: 0;
      padding-top: 0;
      border-top: none;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 22px;
      color: #111827;
    }
    h3 {
      margin: 14px 0 8px;
      font-size: 16px;
      color: #374151;
    }
    p {
      margin: 0 0 10px;
    }
    ul {
      margin: 8px 0 0;
      padding-left: 22px;
    }
    li {
      margin: 6px 0;
    }
    @media (max-width: 600px) {
      body { padding: 12px; }
      .container { padding: 18px; border-radius: 12px; }
      h2 { font-size: 19px; }
    }
  </style>
</head>
<body>
  <main class="container">
__BODY__
  </main>
</body>
</html>
"""


def to_html(summary: MeetingSummary) -> str:
    """Render as a standalone styled HTML document (same structure as Markdown/plain; CSS differs)."""
    body: list[str] = []
    for block in summary.blocks:
        body.append("    <section>")
        if block.heading:
            body.append(f"      <h2>{escape(block.heading)}</h2>")
        for para in block.paragraphs:
            body.append(f"      <p>{escape(para)}</p>")
        for group in block.groups:
            if group.label:
                body.append(f"      <h3>{escape(group.label)}</h3>")
            body.append("      <ul>")
            body.extend(f"        <li>{escape(it)}</li>" for it in group.items)
            body.append("      </ul>")
        body.append("    </section>")
    return _HTML_DOC.replace("__BODY__", "\n".join(body))


# ── JSON (structured) ────────────────────────────────────────────────────────


def to_json(summary: MeetingSummary) -> str:
    """Serialize the structured summary to pretty-printed JSON (``{mode, blocks:[…]}``)."""
    payload = {
        "mode": summary.mode,
        "blocks": [
            {
                "heading": b.heading,
                "paragraphs": list(b.paragraphs),
                "groups": [{"label": g.label, "items": list(g.items)} for g in b.groups],
            }
            for b in summary.blocks
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ── Markdown → object (parse; also the loose fallback parser) ─────────────────


def _normalize_markdown(text: str) -> str:
    """Normalise loose LLM output (single-``*`` headings, ``* `` bullets) to standard Markdown.

    Loose output uses single ``*`` for both topics and sub-labels, so they all become ``##`` — the
    fallback path therefore yields flat blocks with no group nesting (acceptable for a fallback).
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^\*\*(.+?)\*\*$", r"## \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\*(.+?)\*$", r"## \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\*\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    return text


def parse_summary(markdown: str, mode: str) -> MeetingSummary:
    """Parse (canonical or loose) Markdown into blocks by heading level.

    ``#``/``##`` open a top-level block; ``###``+ open a labeled group; bullets fill the current
    group; other text is block prose. Every heading/label is captured verbatim, so renamed headings
    survive. ``mode`` is unused by the level-based parse but kept for signature parity.
    """
    blocks: list[Block] = []
    heading: str | None = None
    paragraphs: list[str] = []
    groups: list[Group] = []
    group_label: str | None = None
    group_items: list[str] = []
    group_open = False

    def flush_group() -> None:
        nonlocal group_open, group_label, group_items
        if group_open:
            groups.append(Group(label=group_label, items=tuple(group_items)))
            group_open = False
            group_label = None
            group_items = []

    def flush_block() -> None:
        nonlocal heading, paragraphs, groups
        flush_group()
        if heading or paragraphs or groups:
            blocks.append(Block(heading=heading, paragraphs=tuple(paragraphs), groups=tuple(groups)))
        heading = None
        paragraphs = []
        groups = []

    for line in _normalize_markdown(markdown).split("\n"):
        stripped = line.strip()
        hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        bm = re.match(r"^[-*]\s+(.+)$", stripped)
        if hm:
            level, text = len(hm.group(1)), hm.group(2).strip()
            if level <= 2:  # ##/# → new top-level block
                flush_block()
                heading = text
            else:  # ###+ → new group in the current block
                flush_group()
                group_open = True
                group_label = text
        elif bm:
            if not group_open:
                group_open = True
                group_label = None
                group_items = []
            group_items.append(bm.group(1).strip())
        elif stripped:
            flush_group()  # prose ends the current group
            paragraphs.append(stripped)

    flush_block()
    return MeetingSummary(mode=mode, blocks=tuple(blocks))


# ── Plain text → object (the desktop's editable form) ────────────────────────


def _restore_case(heading: str) -> str:
    """Undo ``_upper_heading``: ``ТЕМА ВСТРЕЧИ`` → ``Тема встречи``, ``ТЕМА: A`` → ``Тема: A``.

    Upper-casing is lossy, so this is a best guess for the *other* formats (Markdown/HTML/JSON);
    the plain text itself is unaffected because ``to_plain`` upper-cases again. An all-caps
    acronym inside a heading does not survive.
    """
    if ":" in heading:
        label, rest = heading.split(":", 1)
        return f"{label.capitalize()}:{rest}"
    return heading.capitalize()


def _is_plain_heading(line: str) -> bool:
    """A plain-text section header: its label (before any ``:``) is all upper-case."""
    label = line.split(":", 1)[0]
    return any(ch.isalpha() for ch in label) and label == label.upper()


def parse_plain(text: str, mode: str) -> MeetingSummary:
    """Parse the plain-text form (what ``to_plain`` renders) back into blocks.

    Line rules: ``━`` rules are dropped (sections come from headers), an upper-case line opens a
    block, ``• `` fills the current list, a line ending in ``:`` labels the next list, anything
    else is prose. The guarantee is text idempotence — ``to_plain(parse_plain(t)) == t`` for text
    ``to_plain`` produced — not a faithful round-trip of arbitrary typing (an all-caps sentence
    reads as a header, and heading case is restored heuristically).
    """
    blocks: list[Block] = []
    heading: str | None = None
    paragraphs: list[str] = []
    groups: list[Group] = []
    group_label: str | None = None
    group_items: list[str] = []
    group_open = False

    def flush_group() -> None:
        nonlocal group_open, group_label, group_items
        if group_open:
            if group_items:
                groups.append(Group(label=group_label, items=tuple(group_items)))
            elif group_label:  # a label nobody put bullets under — keep the words as prose
                paragraphs.append(f"{group_label}:")
            group_open = False
            group_label = None
            group_items = []

    def flush_block() -> None:
        nonlocal heading, paragraphs, groups
        flush_group()
        if heading or paragraphs or groups:
            blocks.append(Block(heading=heading, paragraphs=tuple(paragraphs), groups=tuple(groups)))
        heading = None
        paragraphs = []
        groups = []

    for raw in text.split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"━"}:
            continue
        if line.startswith("•"):
            if not group_open:
                group_open = True
                group_label = None
                group_items = []
            group_items.append(line[1:].strip())
        elif _is_plain_heading(line):
            flush_block()
            heading = _restore_case(line)
        elif line.endswith(":"):
            flush_group()
            group_open = True
            group_label = line[:-1].strip()
            group_items = []
        else:
            flush_group()  # prose ends the current list
            paragraphs.append(line)

    flush_block()
    return MeetingSummary(mode=mode, blocks=tuple(blocks))


def parse_summary_text(text: str, mode: str) -> MeetingSummary:
    """Parse an edited summary, whichever form it is in.

    The desktop edits plain text, but history entries written before that change (and the CLI's
    output) hold Markdown — sniff for Markdown markers so reopening an old item still parses.
    """
    if re.search(r"^\s*(#{1,6}\s|[-*]\s)", text, flags=re.MULTILINE):
        return parse_summary(text, mode)
    return parse_plain(text, mode)
