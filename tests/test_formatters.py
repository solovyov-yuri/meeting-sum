import json

from formatters import parse_plain, parse_summary, parse_summary_text, render_markdown, to_html, to_json, to_plain
from models import Block, Group, MeetingSummary
from summary_schema import load_summary_json

# The Meeting Summary.pdf / preview references as a structured object (block model).
MEDIUM = MeetingSummary(
    mode="medium",
    blocks=(
        Block(
            heading="Тема встречи",
            paragraphs=(
                "Обсудили коммуникации по разработке, изменения в реестре нерегламентных изменений "
                "и внедрение проверок качества кода.",
            ),
        ),
        Block(
            heading="Тема: Оценка проверок аксессоров",
            groups=(
                Group(
                    "Ключевые обсуждения",
                    (
                        "Команда уточнила наличие и статус проверок аксессоров.",
                        "Проверки пока не проектировались и взяты в бэклог.",
                        "Нужна оценка объёма реализации для планирования фронта работ.",
                    ),
                ),
                Group(
                    "Решения и задачи",
                    (
                        "Дать оценку объёма реализации до 10 числа.",
                        "Сроки реализации определить после оценки.",
                    ),
                ),
            ),
        ),
        Block(
            heading="Тема: Коммуникации по разработке",
            groups=(
                Group("Ключевые обсуждения", ("Единая площадка по разработке обязательна для всех стримов.",)),
                Group("Решения и задачи", ("Назначить и обеспечить регулярное участие представителей команд.",)),
            ),
        ),
        Block(
            heading="Курьёз встречи",
            paragraphs=(
                "Legacy-потоки сравнили с ранами, которые пока «зашивают бытовой иголкой», "
                "но всё же лучше перейти на стерильные инструменты.",
            ),
        ),
    ),
)


# ── to_plain (Telegram copy-paste layout) — the exact expected text, byte for byte ──


def test_to_plain_medium_matches_telegram_layout() -> None:
    sep = "━" * 20
    expected = "\n\n".join(
        [
            "ТЕМА ВСТРЕЧИ",
            "Обсудили коммуникации по разработке, изменения в реестре нерегламентных изменений "
            "и внедрение проверок качества кода.",
            sep,
            "ТЕМА: Оценка проверок аксессоров",
            "Ключевые обсуждения:\n"
            "• Команда уточнила наличие и статус проверок аксессоров.\n"
            "• Проверки пока не проектировались и взяты в бэклог.\n"
            "• Нужна оценка объёма реализации для планирования фронта работ.",
            "Решения и задачи:\n"
            "• Дать оценку объёма реализации до 10 числа.\n"
            "• Сроки реализации определить после оценки.",
            sep,
            "ТЕМА: Коммуникации по разработке",
            "Ключевые обсуждения:\n• Единая площадка по разработке обязательна для всех стримов.",
            "Решения и задачи:\n• Назначить и обеспечить регулярное участие представителей команд.",
            sep,
            "КУРЬЁЗ ВСТРЕЧИ",
            "Legacy-потоки сравнили с ранами, которые пока «зашивают бытовой иголкой», "
            "но всё же лучше перейти на стерильные инструменты.",
        ]
    )
    assert to_plain(MEDIUM) == expected


def test_to_plain_carries_no_markup() -> None:
    # Telegram gets pasted text as-is: no Markdown/HTML leftovers may reach it.
    out = to_plain(MEDIUM)
    assert not any(ch in out for ch in "#*`<>")
    for line in out.split("\n"):
        assert line == line.strip()  # no leading indentation to mangle the paste


def test_to_plain_keeps_wrapped_prose_as_one_paragraph() -> None:
    # parse_summary yields one "paragraph" per source line, so a soft-wrapped paragraph in the
    # editor must not gain a blank line between its lines when pasted into Telegram.
    s = MeetingSummary(mode="brief", blocks=(Block(heading="Тема встречи", paragraphs=("Первая строка,", "её продолжение.")),))
    assert to_plain(s) == "ТЕМА ВСТРЕЧИ\n\nПервая строка,\nеё продолжение."


def test_to_plain_bare_prose() -> None:
    brief = MeetingSummary(mode="brief", blocks=(Block(paragraphs=("Кратко обсудили сроки.",)),))
    out = to_plain(brief)
    assert out == "Кратко обсудили сроки."
    assert "━" not in out


def test_to_plain_group_label_keeps_a_single_colon() -> None:
    # An LLM (or a user editing the Markdown) may already end the label with ":".
    s = MeetingSummary(mode="medium", blocks=(Block(groups=(Group("Решения и задачи:", ("Пункт.",)),)),))
    assert to_plain(s) == "Решения и задачи:\n• Пункт."


def test_to_plain_skips_empty_groups() -> None:
    s = MeetingSummary(mode="medium", blocks=(Block(heading="Тема: X", groups=(Group("Пусто", ()),)),))
    assert to_plain(s) == "ТЕМА: X"


# ── to_html (common structure — same headings as Markdown/plain) ─────────────


def test_to_html_medium_common_structure() -> None:
    out = to_html(MEDIUM)
    assert out.startswith("<!doctype html>")
    assert "<h1>" not in out
    assert "<h2>Тема встречи</h2>" in out
    assert "<h2>Тема: Оценка проверок аксессоров</h2>" in out
    assert "<h3>Ключевые обсуждения</h3>" in out
    assert "<h3>Решения и задачи</h3>" in out
    assert "<li>Команда уточнила наличие и статус проверок аксессоров.</li>" in out
    assert "<h2>Курьёз встречи</h2>" in out
    assert "<p>Legacy-потоки сравнили с ранами" in out


def test_to_html_escapes_content() -> None:
    s = MeetingSummary(mode="medium", blocks=(Block(heading="A <b> & B", groups=(Group(items=("<тег> и &",)),)),))
    out = to_html(s)
    assert "&lt;тег&gt;" in out
    assert "&amp;" in out


# ── render_markdown + heading-edit round-trips (the feature) ──────────────────


def test_render_markdown_medium() -> None:
    md = render_markdown(MEDIUM)
    assert md.startswith("## Тема встречи\n")
    assert "## Тема: Оценка проверок аксессоров" in md
    assert "### Ключевые обсуждения" in md
    assert "### Решения и задачи" in md
    assert "- Команда уточнила наличие и статус проверок аксессоров." in md


def test_markdown_render_is_idempotent() -> None:
    md = render_markdown(MEDIUM)
    assert render_markdown(parse_summary(md, "medium")) == md


def test_renamed_headings_survive_save():
    # The point of the block model: any heading text a user types survives parse (Save) + render.
    cases = [
        "## Тема: Новое название\n### Ключевые обсуждения\n- пункт",  # topic renamed
        "## Тема: X\n### Основные моменты\n- пункт\n### Что решили\n- задача",  # sub-labels renamed
        "## О чём говорили\nКраткое описание.",  # intro heading renamed
        "## Тема встречи\nвступление\n\n## Забавный момент\nшутка",  # joke heading renamed
    ]
    for md in cases:
        rendered = render_markdown(parse_summary(md, "medium"))
        for line in md.splitlines():
            if line.startswith("#"):
                assert line in rendered, f"heading lost: {line!r}\n{rendered}"


# ── to_json (structured, block shape) ────────────────────────────────────────


def test_to_json_block_structure() -> None:
    data = json.loads(to_json(MEDIUM))
    assert data["mode"] == "medium"
    assert data["blocks"][0]["heading"] == "Тема встречи"
    assert data["blocks"][0]["paragraphs"][0].startswith("Обсудили")
    assert data["blocks"][1]["heading"] == "Тема: Оценка проверок аксессоров"
    assert data["blocks"][1]["groups"][0]["label"] == "Ключевые обсуждения"
    assert data["blocks"][1]["groups"][0]["items"][0].startswith("Команда уточнила")
    assert data["blocks"][-1]["heading"] == "Курьёз встречи"


# ── parse_plain (the desktop's editable form) ────────────────────────────────


def test_plain_round_trip_is_idempotent() -> None:
    # The guarantee for the editable plain text: re-rendering what was parsed changes nothing.
    text = to_plain(MEDIUM)
    assert to_plain(parse_plain(text, "medium")) == text


def test_parse_plain_recovers_the_structure() -> None:
    s = parse_plain(to_plain(MEDIUM), "medium")
    assert [b.heading for b in s.blocks] == ["Тема встречи", "Тема: Оценка проверок аксессоров", "Тема: Коммуникации по разработке", "Курьёз встречи"]
    assert s.blocks[1].groups[0].label == "Ключевые обсуждения"
    assert s.blocks[1].groups[1].items == ("Дать оценку объёма реализации до 10 числа.", "Сроки реализации определить после оценки.")
    # Restored heading case reaches the other formats.
    assert "## Тема встречи" in render_markdown(s)


def test_parse_plain_keeps_a_label_without_bullets() -> None:
    # A label the user left empty must not vanish on save; it degrades to prose and stays stable.
    text = "ТЕМА: A\n\nЗаметки:"
    s = parse_plain(text, "medium")
    assert s.blocks[0].paragraphs == ("Заметки:",)
    assert to_plain(s) == text


def test_parse_plain_ignores_separators_and_blank_lines() -> None:
    s = parse_plain("ТЕМА ВСТРЕЧИ\n\n" + "━" * 20 + "\n\nПрозa.", "brief")
    assert len(s.blocks) == 1
    assert s.blocks[0].paragraphs == ("Прозa.",)


def test_parse_plain_reads_an_upper_case_list_label() -> None:
    # A label the user renamed to caps ("ИТОГИ:", "TODO:") sits flush against its bullets, so it
    # labels the list instead of opening a new section and tearing the bullets off their block.
    text = "ТЕМА: A\n\nИТОГИ:\n• x\n• y"
    s = parse_plain(text, "medium")
    assert [b.heading for b in s.blocks] == ["Тема: A"]
    assert s.blocks[0].groups == (Group("ИТОГИ", ("x", "y")),)
    assert to_plain(s) == text  # no invented ━ separator, no blank line under the label


def test_parse_plain_keeps_prose_ending_in_a_colon_as_prose() -> None:
    # The mirror case: a paragraph that merely ends in a colon is separated from the list by a
    # blank line, so it must not be swallowed as that list's label.
    text = "ТЕМА: A\n\nЗаметки:\n\n• x"
    s = parse_plain(text, "medium")
    assert s.blocks[0].paragraphs == ("Заметки:",)
    assert s.blocks[0].groups == (Group(None, ("x",)),)
    assert to_plain(s) == text


def test_parse_plain_splits_lists_separated_by_a_blank_line() -> None:
    # Two groups in a row (the second unlabeled) are rendered with a blank line between the
    # bullets — that blank line must keep them two lists, not merge them into one.
    text = "ТЕМА: A\n\nИТОГИ:\n• x\n\n• y"
    s = parse_plain(text, "medium")
    assert s.blocks[0].groups == (Group("ИТОГИ", ("x",)), Group(None, ("y",)))
    assert to_plain(s) == text


def test_parse_plain_stays_stable_on_a_hand_added_blank_line() -> None:
    # A blank line typed under a label demotes it to prose (the text renders identically, only the
    # structure the other formats show differs) — the point is that nothing is lost or drifts.
    text = "Ключевые обсуждения:\n\n• x"
    s = parse_plain(text, "medium")
    assert s.blocks[0].paragraphs == ("Ключевые обсуждения:",)
    assert s.blocks[0].groups == (Group(None, ("x",)),)
    assert to_plain(s) == text


# Label/heading shapes a user can reach by editing: caps labels, acronyms, prose with a colon,
# a heading that is itself a colon line, unlabeled and stacked groups, ━-separated sections.
_LABEL_SHAPES = (
    MeetingSummary(mode="medium", blocks=(Block(heading="Тема: A", groups=(Group("ИТОГИ", ("x", "y")),)),)),
    MeetingSummary(mode="medium", blocks=(Block(heading="Тема: A", groups=(Group("TODO", ("x",)),)),)),
    MeetingSummary(mode="medium", blocks=(Block(heading="Тема: A", paragraphs=("Заметки:",), groups=(Group(None, ("x",)),)),)),
    MeetingSummary(mode="medium", blocks=(Block(heading="Итоги:", groups=(Group(None, ("x",)),)),)),
    MeetingSummary(mode="medium", blocks=(Block(groups=(Group("ИТОГИ:", ("x",)), Group(None, ("y",)), Group("Заметки", ("z",)))),)),
    MeetingSummary(mode="medium", blocks=(Block(paragraphs=("Итого:", "продолжение"), groups=(Group("TODO", ("x",)),)),)),
    MeetingSummary(
        mode="detailed",
        blocks=(
            Block(heading="ТЕМА: A", paragraphs=("Проза.",), groups=(Group("ИТОГИ", ("x",)),)),
            Block(heading="Тема: Б", groups=(Group(None, ("y",)), Group("TODO", ("z",)))),
            Block(heading="Курьёз встречи", paragraphs=("Шутка:",)),
        ),
    ),
)


def test_plain_round_trip_is_idempotent_for_every_label_shape() -> None:
    # Property: for anything to_plain itself produced, one save (parse) + re-render changes nothing.
    for summary in _LABEL_SHAPES:
        plain = to_plain(summary)
        assert to_plain(parse_plain(plain, summary.mode)) == plain, f"plain text broke on {plain!r}"


def test_parse_summary_text_picks_the_parser() -> None:
    # Plain text (current editor) vs Markdown (entries written before the switch, and the CLI).
    assert parse_summary_text("ТЕМА ВСТРЕЧИ\n\n• пункт", "medium").blocks[0].groups[0].items == ("пункт",)


# ── render idempotence on line breaks inside the content ─────────────────────

# Content that reaches the model always passes through ``summary_schema`` (LLM JSON, or the base
# .json reopened on export/save), which is where line breaks are collapsed; the parsers themselves
# are line-based and cannot produce a multi-line string. So the fixtures below build the "dirty"
# object the way production would receive it and let that boundary normalise it.
_LINE_BREAKS = ("a\nb", "a\n\nb", "a\r\nb", "a\n- b", "a\n• b", "a\n  \n  b")


def _normalized(*, marker: str) -> MeetingSummary:
    """A summary whose every string slot carries ``marker``, healed through the schema boundary."""
    dirty = MeetingSummary(
        mode="medium",
        blocks=(
            Block(
                heading=f"Тема: {marker}",
                paragraphs=(f"Проза {marker}",),
                groups=(Group(f"Метка {marker}", (f"пункт {marker}", "обычный пункт")),),
            ),
            Block(heading="Главное", groups=(Group(None, (f"итог {marker}",)),)),
        ),
    )
    return load_summary_json(to_json(dirty))


def test_line_break_in_a_list_item_keeps_the_block_structure() -> None:
    # The reported case: the tail of a multi-line item used to re-parse as prose of the block,
    # so the item lost half its text and the next render moved it.
    summary = _normalized(marker="line1\nline2")
    group = summary.blocks[0].groups[0]
    assert group.items == ("пункт line1 line2", "обычный пункт")
    assert summary.blocks[0].paragraphs == ("Проза line1 line2",)  # nothing leaked into the prose

    md = render_markdown(summary)
    assert "- пункт line1 line2" in md
    assert render_markdown(parse_summary(md, "medium")) == md

    plain = to_plain(summary)
    assert "• пункт line1 line2" in plain
    assert to_plain(parse_plain(plain, "medium")) == plain


def test_renders_stay_idempotent_for_every_line_break_shape() -> None:
    # Both editable forms round-trip exactly, whatever line break the content carried.
    for marker in _LINE_BREAKS:
        summary = _normalized(marker=marker)
        md = render_markdown(summary)
        assert render_markdown(parse_summary(md, "medium")) == md, f"markdown broke on {marker!r}"
        plain = to_plain(summary)
        assert to_plain(parse_plain(plain, "medium")) == plain, f"plain text broke on {marker!r}"
        assert "\\n" not in to_json(summary), marker  # no escaped line break survives into the .json
    assert parse_summary_text("## Тема встречи\n- пункт", "medium").blocks[0].groups[0].items == ("пункт",)
