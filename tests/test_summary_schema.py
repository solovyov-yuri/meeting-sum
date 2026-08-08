import pytest

from formatters import to_json
from models import Block, Group, MeetingSummary
from summary_schema import SummaryValidationError, load_summary_json, parse_summary_json

# ── parse_summary_json: rich LLM JSON → blocks ───────────────────────────────


def test_maps_rich_json_to_blocks() -> None:
    raw = """
    {
      "intro": "О встрече",
      "sections": [{"title": "Тема А", "points": ["п1", "п2"], "actions": ["сделать"]}],
      "joke": "ха-ха"
    }
    """
    got = parse_summary_json(raw, "medium")
    assert got == MeetingSummary(
        mode="medium",
        blocks=(
            Block(heading="Тема встречи", paragraphs=("О встрече",)),
            Block(
                heading="Тема: Тема А",
                groups=(
                    Group("Ключевые обсуждения", ("п1", "п2")),
                    Group("Решения и задачи", ("сделать",)),
                ),
            ),
            Block(heading="Курьёз встречи", paragraphs=("ха-ха",)),
        ),
    )


def test_detailed_points_label_and_action_owner_due() -> None:
    raw = '{"sections": [{"title": "T", "points": ["p"], "actions": [{"text": "чинить", "owner": "Ян", "due": "пт"}]}]}'
    got = parse_summary_json(raw, "detailed")
    block = got.blocks[0]
    assert block.groups[0].label == "Ход обсуждения"  # detailed points label
    assert block.groups[1].items == ("чинить — Ян — пт",)  # owner/due folded into text


def test_strips_code_fence_and_think() -> None:
    raw = '<think>reasoning</think>\n```json\n{"intro": "Кратко"}\n```'
    got = parse_summary_json(raw, "brief")
    assert got.blocks == (Block(heading="Тема встречи", paragraphs=("Кратко",)),)


def test_invalid_json_raises() -> None:
    with pytest.raises(SummaryValidationError):
        parse_summary_json("not json at all", "medium")


def test_wrong_type_raises() -> None:
    with pytest.raises(SummaryValidationError):
        parse_summary_json('{"sections": "should be a list"}', "medium")


def test_empty_summary_raises() -> None:
    with pytest.raises(SummaryValidationError):
        parse_summary_json('{"intro": null, "sections": []}', "medium")


# ── load_summary_json: our block JSON ↔ to_json ──────────────────────────────


def test_load_summary_json_round_trips_to_json() -> None:
    obj = MeetingSummary(
        mode="detailed",
        blocks=(
            Block(heading="Тема встречи", paragraphs=("Вступление",)),
            Block(heading="Тема: T", groups=(Group("Метка", ("a", "b")), Group(None, ("c",)))),
        ),
    )
    assert load_summary_json(to_json(obj)) == obj


def test_collapses_line_breaks_in_every_string() -> None:
    # Renderers and parsers are line-based, so a newline inside any string would re-parse as a
    # different block. The model is kept single-line by construction instead.
    raw = """
    {
      "intro": "первая\\n\\nвторая",
      "participants": ["Ян\\nПетров"],
      "sections": [{
        "title": "Тема\\nдлинная",
        "points": ["п1\\nхвост"],
        "actions": [{"text": "сделать\\nвсё", "owner": "Ян\\nП"}, "строкой\\r\\nвторой"]
      }],
      "takeaways": ["итог\\n- подпункт"],
      "joke": "ха\\nха"
    }
    """
    got = parse_summary_json(raw, "medium")
    assert got == MeetingSummary(
        mode="medium",
        blocks=(
            Block(heading="Участники", groups=(Group(None, ("Ян Петров",)),)),
            Block(heading="Тема встречи", paragraphs=("первая вторая",)),
            Block(
                heading="Тема: Тема длинная",
                groups=(
                    Group("Ключевые обсуждения", ("п1 хвост",)),
                    Group("Решения и задачи", ("сделать всё — Ян П", "строкой второй")),
                ),
            ),
            Block(heading="Главное", groups=(Group(None, ("итог - подпункт",)),)),
            Block(heading="Курьёз встречи", paragraphs=("ха ха",)),
        ),
    )


def test_load_summary_json_heals_line_breaks_in_an_existing_file() -> None:
    # A base .json written before the normalisation (or hand-edited) must come back single-line,
    # so reopening it for export cannot move an item's tail into the block's prose.
    got = load_summary_json(
        '{"mode": "medium", "blocks": [{"heading": "Тема:\\nX", "paragraphs": ["проза\\n\\nещё"],'
        ' "groups": [{"label": "Метка\\nM", "items": ["line1\\nline2"]}]}]}'
    )
    assert got.blocks == (
        Block(
            heading="Тема: X",
            paragraphs=("проза ещё",),
            groups=(Group("Метка M", ("line1 line2",)),),
        ),
    )


def test_load_summary_json_empty_on_old_rich_format() -> None:
    # An old {mode, intro, sections} base .json has no "blocks" key → empty (signals the caller to
    # fall back to re-parsing the Markdown).
    got = load_summary_json('{"mode": "medium", "intro": "старое", "sections": []}')
    assert got.mode == "medium"
    assert got.blocks == ()
