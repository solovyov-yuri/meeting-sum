---
id: CODE-006
title: "Реальная транскрибация не сообщает percent — прогресс-бар работает только в demo-моке"
category: CODE
severity: low
effort: small
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/workflows.py
    anchor: "Транскрибация началась."
    line_hint: 248
  - path: desktop/src/lib/bridge.ts
    anchor: "percent"
    line_hint: 217
  - path: src/providers/whisper.py
    anchor: "Progress"
    line_hint: 98
---

# CODE-006: `ProgressEvent.percent` мёртв в реальном пути

## Проблема

Единственное событие транскрибации — `ProgressEvent(STEP_TRANSCRIBE, "running", "Транскрибация
началась.")`; `percent` в workflows не выставляется никогда. Browser-мок при этом изображает
25/55/85% (`bridge.ts:~217-221`). Данные для реального процента уже есть в
`WhisperTranscriber.transcribe` (segment `end` vs `info.duration`, rich-бар ~98-110 — уходит в
отбрасываемый stderr, см. [[ARCH-004]]).

## Почему это важно

Транскрибация — самый долгий этап; UI минутами показывает неопределённое состояние, тогда как
demo-режим обещает движущийся бар.

## Варианты решения

1. **Рекомендуется:** опциональный per-segment колбэк в `WhisperTranscriber.transcribe`, проброс `percent` через прогресс-колбэк `run_one_file`. Компромисс: меняется сигнатура провайдера.
2. Убрать `percent` из мока, чтобы не обещать лишнего (quick-win, хуже UX).

## Как проверить исправление

Реальный запуск в десктопе показывает растущий процент на этапе транскрибации.
