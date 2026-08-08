---
id: ARCH-005
title: "resummarize принимает cancel_flag, но игнорирует отмену — «Остановить» не работает в режимах суммаризации"
category: ARCH
severity: medium
effort: small
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/desktop_bridge.py
    anchor: "noqa: ARG001 - accepted for a uniform streaming signature"
    line_hint: 676
  - path: src/workflows.py
    anchor: "def resummarize_one"
    line_hint: 462
  - path: desktop/src-tauri/src/lib.rs
    anchor: "cancel_flag"
    line_hint: 258
  - path: docs/desktop-bridge-contract.md
    anchor: "cancel_flag"
---

# ARCH-005: Отмена resummarize — мёртвый вход контракта

## Проблема

Вся цепочка отмены для `resummarize` собрана: Rust создаёт flag-файл и watcher-поток, UI при
нажатии «Остановить» логирует «Остановка произойдёт после завершения текущего этапа», контракт §6
обещает проверку флага «на каждый run_recap/**resummarize**». Но Python-сторона выбрасывает флаг:

```python
cancel: workflows.CancelCheck | None = None,  # noqa: ARG001 - accepted for a uniform streaming signature
```

а `workflows.resummarize_one` вообще не имеет параметра `cancel` и ни разу не опрашивает флаг.
Запуски в режимах «Суммаризация» и «Повторить суммаризацию» остановить нельзя даже на границе
шага (например, до LLM-вызова); результат запишется в историю как `success` после нажатия
«Остановить».

## Доказательства

Grep `ARG001` в `src/desktop_bridge.py` + чтение `resummarize_one` целиком (2026-07-05): ни
одного обращения к `cancel`. Прошлый фикс отмены ([[ARCH-002]]) покрыл только `run_one_file`.

## Почему это важно

Прямое нарушение задокументированного контракта (§6) и обещания UI; Rust держит watcher-поток
впустую. Это тот же класс «dead contract input», что и закрытый ARCH-003.

## Варианты решения

1. **(Рекомендуется)** Прокинуть `cancel: CancelCheck | None` в `resummarize_one` и проверять
   флаг на тех же границах, что в `run_one_file` (перед `make_summarizer`, перед
   `_summarize_and_export`), возвращая `RunResult("cancelled", …)`; в мосте убрать `noqa: ARG001`
   и передать аргумент.
2. Минимум: убрать `cancel_flag` из resummarize-контракта и скрыть «Остановить» в этом режиме —
   хуже: теряется отмена до начала LLM-вызова, и §6 придётся переписывать.

## Как проверить исправление

Unit-тест: `resummarize(payload, cancel=lambda: True)` → `status == "cancelled"`, история не
содержит `success`-записи. Вручную — «Остановить» во время «Суммаризация» в живом app
(Windows-сторона).

## Связанные

[[ARCH-002]] — кооперативная отмена run_one_file (образец); [[ARCH-003]] — прежний мёртвый вход.
