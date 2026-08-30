---
id: CODE-003
title: "workflows.transcribe_audio и summarize_transcript — мёртвый код, дублирующий run_one_file"
category: CODE
severity: low
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: [ARCH-001]
locations:
  - path: src/workflows.py
    anchor: "def transcribe_audio"
    line_hint: 115
  - path: src/workflows.py
    anchor: "def summarize_transcript"
    line_hint: 143
---

# CODE-003: Мёртвые функции в workflows.py

## Проблема

`transcribe_audio` и `summarize_transcript` не имеют ни одного вызова в src/ и tests/ (проверено
grep); `run_one_file` дублирует их тела инлайн (блок preprocess+transcribe ~243-249 повторяет
`transcribe_audio` ~134-140). Третья копия последовательности транскрибации.

## Варианты решения

1. Удалить обе функции.
2. **Предпочтительно при работе над [[ARCH-001]]:** заставить `run_one_file` вызывать их — унифицирует дубли.

## Как проверить исправление

Либо функций нет, либо `run_one_file` их вызывает; тесты зелёные.
