---
id: CODE-004
title: "Мелкий копипаст и мусор: дубликат в кортеже humanize_error, no-op re-raise, дублированные privacy/history-блоки"
category: CODE
severity: low
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/workflows.py
    anchor: "\"APIConnectionError\", \"ConnectionError\", \"APIConnectionError\""
    line_hint: 104
  - path: src/desktop_bridge.py
    anchor: "raise ConfigError(str(exc)) from exc"
    line_hint: 193
  - path: src/desktop_bridge.py
    anchor: "is_external_provider"
    line_hint: 371
  - path: desktop/src/lib/bridge.ts
    anchor: "runRecap"
    line_hint: 277
---

# CODE-004: Пакет мелких дефектов кода

## Проблема

1. `workflows.py:104` — `if name in ("APIConnectionError", "ConnectionError", "APIConnectionError")`:
   первый и третий элементы кортежа одинаковы. Возможно, вместо дубля имелся в виду другой класс
   (`APIStatusError`?) — решить при исправлении.
2. `desktop_bridge.py:193-194` — `except ConfigError as exc: raise ConfigError(str(exc)) from exc`:
   бессмысленный re-raise того же типа.
3. `desktop_bridge.py:~371-379 и ~401-409` — идентичные 9-строчные блоки privacy-warning в
   `run_recap`/`resummarize` → вынести `_maybe_emit_privacy_warning(...)`.
4. `desktop/src/lib/bridge.ts:~277-296 и ~347-366` — два идентичных ~20-строчных литерала записи
   истории в browser-моке → хелпер `pushHistory(result, req)`.

## Почему это важно

Каждый пункт по отдельности безобиден; вместе — типичный дрейф-риск копипаста.

## Как проверить исправление

grep по перечисленным якорям; тесты и `npm run test` зелёные.
