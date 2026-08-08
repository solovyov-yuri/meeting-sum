---
id: ARCH-003
title: "Вход контракта output_formats мёртв: RunOptions.output_format никогда не читается"
category: ARCH
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/workflows.py
    anchor: "output_format: str = \"telegram\""
    line_hint: 48
  - path: src/desktop_bridge.py
    anchor: "formats[0] if formats else"
    line_hint: 321
  - path: desktop/src/hooks/useRecap.ts
    anchor: "output_formats"
    line_hint: 168
  - path: docs/desktop-bridge-contract.md
    anchor: "output_formats"
    line_hint: 218
---

# ARCH-003: `output_formats` — мёртвый вход контракта

## Проблема

Фронтенд шлёт `output_formats: ["telegram", "json"]` (`useRecap.ts:~168, ~228`), мост сворачивает
его в `RunOptions.output_format = formats[0]` (`desktop_bridge.py:~321-328`), а workflow это поле
**нигде не читает**: `_summarize_and_export` безусловно пишет telegram `.txt` + `.json`
(`workflows.py:~327-330`). Поле задокументировано в контракте как рабочий вход.

## Почему это важно

Документированный вход не имеет эффекта: запрос `["plain"]` молча выдаст telegram+json. Мёртвый
плюмбинг провоцирует неверные предположения при доработках.

## Варианты решения

1. **Рекомендуется:** удалить `output_format` из `RunOptions` и `output_formats` из входа `run_recap` в контракте и фронтенде (выбор формата уже покрыт `export_summary`). Честно и дёшево.
2. Реально поддержать список в `_summarize_and_export`. Компромисс: больше вариантов результата (`summary_path` может стать null при json-only).

## Как проверить исправление

`grep -rn "output_format" src/ desktop/src docs/` — либо поле исчезло везде, либо реально влияет на набор записанных файлов (тест в `tests/test_workflows.py`).

## Связанные

[[DOC-001]], [[CODE-004]].
