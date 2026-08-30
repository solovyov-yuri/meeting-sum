---
id: AGENT-004
title: "Глобальный CLAUDE.md обязывает вызывать скилл graphify, недоступный из WSL-окружения (двойной .claude-home)"
category: AGENT
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: /mnt/c/Users/solov/.claude/CLAUDE.md
    anchor: "graphify"
---

# AGENT-004: /graphify-триггер указывает на нерабочий путь

## Проблема

Глобальный `/mnt/c/Users/solov/.claude/CLAUDE.md` требует: «When the user types `/graphify`,
invoke the Skill tool with skill: "graphify"». Файлы скилла существуют в Windows-home
(`/mnt/c/Users/solov/.claude/skills/graphify/`), но Claude Code в WSL использует home
`/home/samogonn/.claude`, чей `skills/` пуст — `graphify` не появляется в списке доступных
скиллов, и предписанный вызов Skill-тула завершится ошибкой.

Это тот же корневой сплит Windows-home/WSL-home, что породил три копии project-review
([[AGENT-001]]).

## Варианты решения

1. **Рекомендуется:** symlink/копия graphify в `/home/samogonn/.claude/skills/`.
2. Системно: единый `.claude`-home через `CLAUDE_CONFIG_DIR` для обеих сторон.
3. Убрать триггер из глобального CLAUDE.md на WSL-стороне.

## Как проверить исправление

`graphify` присутствует в списке доступных скиллов новой сессии; `/graphify` отрабатывает.

## Связанные

[[AGENT-001]].
