---
id: CODE-011
title: "serve() дублирует стриминг-обвязку _streaming(): разбор cancel_flag и терминальное фреймирование скопированы"
category: CODE
severity: low
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/desktop_bridge.py
    anchor: "def _streaming"
    line_hint: 743
  - path: src/desktop_bridge.py
    anchor: "def serve"
    line_hint: 780
---

# CODE-011: Копипаст между spawn-per-call и warm-worker путями

## Проблема

`serve()` (persistent worker) копирует из `_streaming()` разбор `cancel_flag`
(`payload.pop(...)` → `Path(flag).exists`), try/except-границу и терминальное фреймирование
(`_emit_line({"type": "result"/"error", ...})`). Два места обязаны эволюционировать синхронно:
например, фикс [[ARCH-005]] (прокинуть cancel в resummarize) надо будет не забыть в обоих —
расхождение сломает либо spawn-per-call, либо warm-worker путь незаметно для другого. Мелочь
рядом: `check_model` локально реимпортирует `PROVIDER_PRESETS`, уже импортированный на уровне
модуля.

## Доказательства

`src/desktop_bridge.py` — параллельные фрагменты в `_streaming` и в теле цикла `serve`
(2026-07-05).

## Почему это важно

Прошлое ревью уже фиксировало этот класс проблем (ARCH-001: продублированный пайплайн разошёлся
поведением). Дешевле схлопнуть сейчас, пока пути идентичны.

## Варианты решения

1. **(Рекомендуется)** Выделить хелпер `_run_streaming_request(runner, payload, emit)` (pop flag →
   build cancel → try/except → emit result/error) и вызвать из `_streaming` и из цикла `serve`;
   убрать лишний импорт в `check_model`.

## Как проверить исправление

`pytest tests/test_desktop_bridge.py` зелёный, включая `test_serve_reuses_transcriber_across_runs`.

## Связанные

[[ARCH-005]], [[PERF-001]] — источник второго пути.
