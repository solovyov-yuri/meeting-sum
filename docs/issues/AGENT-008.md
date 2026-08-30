---
id: AGENT-008
title: "Весь .claude/ в gitignore — проектный скилл и allowlist существуют только на этой машине"
category: AGENT
severity: low
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: .gitignore
    anchor: ".claude/"
---

# AGENT-008: .claude/ не версионируется целиком

## Проблема

Последняя строка `.gitignore` — `.claude/`. В git отслеживаются только AGENTS.md, CLAUDE.md,
`docs/desktop-agent-checklist.md`; `.claude/skills/project-review/` и allowlist разрешений живут
только локально. Для соло-проекта терпимо, но это прямо способствует расхождению копий
([[AGENT-001]]) и означает потерю скилла/allowlist при переклоне.

## Варианты решения

1. Сузить ignore до `.claude/settings.local.json`, отслеживать `.claude/skills/` (и опционально общий `.claude/settings.json`).

## Как проверить исправление

`git ls-files .claude/` показывает skills; `settings.local.json` остаётся неотслеживаемым.

## Связанные

[[AGENT-001]].
