---
id: CONV-001
title: "ruff isort known-first-party: призрачные модули pipeline/protocols, отсутствует preprocessing"
category: CONV
severity: low
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: pyproject.toml
    anchor: "known-first-party"
    line_hint: 50
---

# CONV-001: Устаревший known-first-party в ruff

## Проблема

`known-first-party` перечисляет `pipeline` и `protocols`, которых в `src/` нет, и не содержит
реального модуля `preprocessing` (`src/preprocessing.py`). Будущий top-level
`import preprocessing` будет отсортирован ruff'ом в third-party-группу — I001-шум; призрачные
записи — след переименованного дизайна.

## Варианты решения

1. Заменить `pipeline`/`protocols` на `preprocessing`.

## Как проверить исправление

Список совпадает с `ls src/*.py`; `ruff check src/` зелёный.
