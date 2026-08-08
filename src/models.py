from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Group:
    """A labeled bullet list inside a block (e.g. «Ключевые обсуждения»). ``label`` is free text."""

    label: str | None = None
    items: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Block:
    """A top-level section: a free-text heading, prose paragraphs, and labeled sub-lists.

    Content is normalized to paragraphs-then-groups (prose interleaved after a list is hoisted
    before it on save — an accepted simplification of the editable-text model).
    """

    heading: str | None = None
    paragraphs: tuple[str, ...] = field(default_factory=tuple)
    groups: tuple[Group, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MeetingSummary:
    """Structured meeting summary — the single source of truth for every output format.

    A flat list of blocks with free-text headings/labels, so any heading a user types in the editor
    survives save→export. Produced by validating the LLM's rich JSON (``summary_schema``) or by
    parsing an edited summary back (``formatters.parse_summary``/``parse_plain``); rendered to Markdown / plain /
    HTML / JSON by ``formatters``. All collections are tuples so the whole object is immutable.
    """

    mode: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)
