---
id: CONV-002
title: "ruff known-first-party снова отстал: нет summary_schema, cuda_support, ollama_support — список дрейфует второй раз подряд"
category: CONV
severity: low
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: pyproject.toml
    anchor: "known-first-party"
    line_hint: 53
---

# CONV-002: Ручной first-party-список дрейфует при каждом новом модуле

## Проблема

Прошлое ревью уже чинило этот список ([[CONV-001]]: призраки `pipeline`/`protocols`, отсутствовал
`preprocessing`). За три дня он отстал снова — три новых модуля (`summary_schema`, `cuda_support`,
`ollama_support`) в него не добавлены. Сейчас это безвредно (`src = ["src"]` классифицирует их
first-party автоматически, ruff зелёный), но список ложно-исчерпывающий, и при рефакторинге
конфига сортировка импортов молча поедет.

Повторение за один цикл показывает: ручной список — неправильный механизм.

## Варианты решения

1. **(Рекомендуется)** Удалить `known-first-party` целиком, положившись на автодетекцию через
   `src = ["src"]`, — класс проблемы исчезает.
2. Дописать три имени (симптоматично: отстанет снова).

## Как проверить исправление

`.venv/Scripts/ruff.exe check src/` и `ruff.exe format --check src/` — зелёные; diff импортов
пуст.

## Связанные

[[CONV-001]] — первое проявление того же дрейфа.
