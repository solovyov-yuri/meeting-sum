---
id: CODE-002
title: "run_one_file строит summarizer дважды (валидация + исполнение)"
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
    anchor: "make_summarizer"
    line_hint: 221
  - path: src/workflows.py
    anchor: "_summarize_and_export"
    line_hint: 316
---

# CODE-002: Двойное построение summarizer

## Проблема

`run_one_file` вызывает `make_summarizer(...)` для ранней валидации и выбрасывает результат
(~221), затем `_summarize_and_export` строит его заново (~316). Сегодня конструктор дёшев, но два
места конструирования провоцируют дрейф (валидация и исполнение могут разойтись).

## Варианты решения

1. **Рекомендуется:** построить один раз и передать инстанс в `_summarize_and_export`.
2. Либо завести явный `validate_summarizer_options()` в фабрике.

## Как проверить исправление

`grep -n "make_summarizer" src/workflows.py` — один вызов на запуск; тесты workflows зелёные.
