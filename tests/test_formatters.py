import json

from formatters import parse_plain, parse_summary, parse_summary_text, render_markdown, to_html, to_json, to_plain
from models import Block, Group, MeetingSummary

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


def test_parse_summary_text_picks_the_parser() -> None:
    # Plain text (current editor) vs Markdown (entries written before the switch, and the CLI).
    assert parse_summary_text("ТЕМА ВСТРЕЧИ\n\n• пункт", "medium").blocks[0].groups[0].items == ("пункт",)
    assert parse_summary_text("## Тема встречи\n- пункт", "medium").blocks[0].groups[0].items == ("пункт",)
