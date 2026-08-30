---
id: PERF-001
title: "Whisper-модель загружается с нуля на каждый десктоп-запуск (spawn-per-command)"
category: PERF
severity: medium
effort: large
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: desktop/src-tauri/src/lib.rs
    anchor: "streaming_blocking"
    line_hint: 179
  - path: src/providers/whisper.py
    anchor: "WhisperModel(model_name"
    line_hint: 76
---

# PERF-001: Модель Whisper перезагружается на каждый запуск

## Проблема

Мост по дизайну spawn-per-command (`lib.rs`, док-коммент ~3-6): каждый запуск — новый процесс →
`make_transcriber` → `WhisperModel(...)` → полная загрузка модели + инициализация CUDA
(~10-60 с для large-v3). CLI `batch` при этом переиспользует один transcriber на все файлы
(`cli.py:146`). Для коротких встреч загрузка модели доминирует над полезной работой.
(`resummarize` transcriber не строит — это уже хорошо.)

## Варианты решения

1. Долгоживущий bridge-демон с request/response через stdio — large, максимальный выигрыш UX.
2. Оставить spawn-per-run, задокументировать стоимость; следить, чтобы кэш модели лежал на быстром диске — бесплатно.

## Как проверить исправление

Второй запуск подряд в десктопе стартует транскрибацию без многосекундной паузы загрузки модели.
