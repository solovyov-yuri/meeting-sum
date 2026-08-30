---
id: PERF-002
title: "Чанковая суммаризация полностью последовательная"
category: PERF
severity: low
effort: medium
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/providers/llm.py
    anchor: "_chunked_summarize"
    line_hint: 143
---

# PERF-002: Последовательные вызовы LLM по чанкам

## Проблема

`_chunked_summarize` обрабатывает чанки в цикле (`llm.py:143-147`): 5-чанковый транскрипт стоит
5× латентности LLM + merge-вызов, хотя чанки независимы.

## Варианты решения

1. `ThreadPoolExecutor(max_workers=2-3)` для чанков, merge последовательный. Компромиссы: ломает текущий стриминг токенов в stderr; на локальном Ollama упрётся в ресурсы — гейтить по провайдеру.
2. Принять как есть для локальных провайдеров (частый кейс) — задокументировать.

## Как проверить исправление

Замер wall-clock на многочанковом транскрипте против внешнего провайдера.
