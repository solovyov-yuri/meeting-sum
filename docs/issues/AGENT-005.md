---
id: AGENT-005
title: "Allowlist разрешений не соответствует документированному workflow; нет deny-правила для uv"
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
  - path: .claude/settings.local.json
    anchor: "pytest.exe -q"
---

# AGENT-005: Разрешения рассинхронизированы с workflow

## Проблема

`.claude/settings.local.json` (проверено):

- Разрешены ровно `pytest.exe -q` и одна замороженная строка с тремя конкретными тест-файлами, но
  канонический вариант из CLAUDE.md — `pytest.exe -v` — **не** разрешён → промпт на каждый
  документированный запуск тестов.
- Разрешён `Bash(.venv/Scripts/python.exe *)`, который и так покрывает pytest
  (`python.exe -m pytest`) — тонкая нарезка pytest-правил ничего не защищает.
- Отсутствуют: `recap.exe`, `ruff.exe format`, `npm run lint|test|build` (при живом
  desktop-workflow; разово внесены только `npm --version`/`cargo --version`).
- Избыточно: `Read(//mnt/c/Users/solov/.claude/skills/graphify/**)` покрыт соседним `skills/**`.
- **Нет `deny` для `uv`**, хотя «uv из WSL корёжит Windows-venv» — главная環境-опасность по
  CLAUDE.md; защита держится только на прозе.

## Почему это важно

Промпты приходятся ровно на благословлённые команды — тренируют кликать «разрешить»; единственное
правило, механически предотвращающее реальный ущерб (uv), отсутствует.

## Варианты решения

1. **Рекомендуется:** заменить pytest-записи на `Bash(.venv/Scripts/pytest.exe *)`; добавить `ruff.exe *`, `mypy.exe *`, `recap.exe *`, нужные `npm run …`; добавить `"deny": ["Bash(uv *)"]`; удалить избыточное graphify-правило.
2. Сгенерировать allowlist скиллом `fewer-permission-prompts` по транскриптам.

## Как проверить исправление

`.venv/Scripts/pytest.exe -v` и `ruff format` не вызывают промптов; `uv sync` блокируется deny-правилом.
