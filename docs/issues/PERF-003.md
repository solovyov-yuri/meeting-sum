---
id: PERF-003
title: "_extract_dlls читает каждую DLL целиком в память (сотни МБ) и не опрашивает cancel во время распаковки"
category: PERF
severity: low
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/cuda_support.py
    anchor: "out.write(src.read())"
    line_hint: 95
  - path: src/cuda_support.py
    anchor: "def download_cuda_libs"
    line_hint: 112
---

# PERF-003: Пиковая память и глухая к отмене фаза распаковки CUDA

## Проблема

`_extract_dlls` пишет члены wheel-а через `out.write(src.read())` — отдельные DLL в cuDNN/cuBLAS
достигают сотен МБ (сам win-wheel cuBLAS — 553 МБ), что даёт пик RAM в сотни мегабайт именно на
слабых машинах, где portable-сборку и запускают. Кроме того, `check_cancel()` опрашивается только
в цикле скачивания: фаза «Распаковка…» (десятки секунд на HDD) на кнопку отмены не реагирует.
Состояние при этом консистентно (сентинел не записан), но UX-ощущение — зависшая отмена.

## Доказательства

`src/cuda_support.py` прочитан целиком (2026-07-05): `src.read()` без чанков; `check_cancel` — в
`download_cuda_libs`, в `_extract_dlls` не пробрасывается.

## Варианты решения

1. **(Рекомендуется)** `shutil.copyfileobj(src, out, 1 << 20)` + проброс `check_cancel` в
   `_extract_dlls` с вызовом в цикле копирования.

## Как проверить исправление

Существующие тесты `test_cuda_support.py` зелёные + новый тест: cancel во время extract →
`DownloadCancelled`, сентинел отсутствует.

## Связанные

[[SEC-008]] — та же функция; [[REL-009]] — симметричная глухота к cancel в Ollama-pull.
