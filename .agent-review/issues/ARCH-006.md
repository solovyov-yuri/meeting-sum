---
id: ARCH-006
title: "Round-trip render_markdown → parse_summary не точен: \\n внутри элемента списка перетекает в прозу чужого блока при сохранении/экспорте"
category: ARCH
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/formatters.py
    anchor: '"\n".join(f"- {it}"'
    line_hint: 54
  - path: src/summary_schema.py
    anchor: "_str_list"
    line_hint: 83
  - path: src/formatters.py
    anchor: "render idempotence"
    line_hint: 20
---

# ARCH-006: Инвариант render/parse round-trip нарушается на многострочных элементах списка

## Проблема

AGENTS.md объявляет round-trip «постоянным» инвариантом («keep the render/parse round-trip
exact»), и `formatters.py` заявляет «render idempotence — render(parse(render(obj))) ==
render(obj)». Но `render_markdown` вставляет элементы списка без экранирования, а
`summary_schema._str_list`/`load_summary_json` пропускают строки с внутренними `\n` (реальный
выход LLM-JSON). Воспроизведено на venv-питоне репозитория (2026-07-05):

```
render:  '## Темы встречи\n\n- line1\nline2'
reparse: items=('line1',), paragraphs=('line2',)
render2: '## Темы встречи\nline2\n\n- line1'   # ROUNDTRIP BROKEN
```

После «Сохранить» (`save_summary` пересобирает `.json` из Markdown) или экспорта хвост элемента
списка становится абзацем блока — тихая порча данных пользователя.

## Доказательства

Скрипт-репро выше; `test_markdown_render_is_idempotent` это не ловит, т.к. проверяет только
канонические однострочные формы.

## Почему это важно

Это единственный заявленный инвариант пайплайна структурированного саммари; на нём держатся
редактирование и все четыре экспортных формата. Порча тихая: пользователь видит её только
пересмотрев сохранённый файл.

## Варианты решения

1. **(Рекомендуется)** Нормализовать на входе в модель: в `summary_schema._clean_str`/`_str_list`
   (и в `load_summary_json`) схлопывать внутренние `\n` в пробел — весь объект по построению
   однострочен, рендер не меняется.
2. Защитно экранировать в `render_markdown` (`it.replace("\n", " ")`) — латает рендер, но
   «грязные» объекты продолжают жить в `.json`.
3. Дополнительно: property-тест `render(parse(render(x))) == render(x)` на генерируемых
   `MeetingSummary` — закрепляет инвариант навсегда.

## Как проверить исправление

Регресс-тест с `items=("line1\nline2",)` → после parse(render(…)) структура блоков стабильна,
render идемпотентен. Существующие тесты `test_formatters.py`/`test_summary_schema.py` зелёные.

## Связанные

[[REL-013]] — соседний путь экспорта из битого `.json`.
