---
id: AGENT-015
title: "Относительные allow-паттерны могут не покрывать составные вызовы (cd desktop && npm …, абсолютные пути к venv-бинарям)"
category: AGENT
severity: low
effort: quick-win
status: proposed
evidence: hypothesis
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: .claude/settings.local.json
    anchor: "Bash(npm run lint"
---

# AGENT-015: Возможные остаточные permission-промпты на blessed-командах

## Проблема

Frontend-команды требуют cwd `desktop/`; вызов `cd desktop && npm run lint` или абсолютный путь
`/mnt/c/.../recap/.venv/Scripts/pytest.exe` может не матчиться префиксными правилами
(`Bash(npm run lint*)`, `Bash(.venv/Scripts/pytest.exe *)`) — тогда blessed-workflow снова
промптит. В просмотренных сессиях после 02.07 явных отказов по этим командам не найдено (только
4 корректных classifier-denial по self-modification прав), поэтому `evidence: hypothesis`.

## Варианты решения

1. **(Рекомендуется)** Наблюдать; при первом же промпте на канонической команде добавить
   недостающий вариант паттерна (не раздувать список превентивно). Удобно совместить с переносом
   в общий settings.json ([[AGENT-014]]).
2. Заранее добавить абсолютно-путевые и `cd desktop &&`-дубли.

## Как проверить исправление

В свежей сессии `cd desktop && npm run lint` и абсолютный вызов pytest проходят без промпта.

## Связанные

[[AGENT-014]], [[AGENT-005]].
