---
id: AGENT-014
title: "Allowlist и deny-правило uv живут только в машинно-локальном settings.local.json; обещанный в .gitignore общий settings.json не создан"
category: AGENT
severity: low
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: .claude/settings.local.json
    anchor: "permissions"
  - path: .gitignore
    anchor: "settings.local.json"
    line_hint: 22
---

# AGENT-014: Права не версионируются вопреки собственному замыслу

## Проблема

Сужение gitignore (02.07, [[AGENT-008]]) сделано ровно для того, чтобы версионировать общий
`.claude/settings.json` (комментарий в `.gitignore` это прямо обещает). Но allowlist (канонические
команды) и `deny Bash(uv *)` остались только в `settings.local.json` — единственном файле в
`.claude/`. На другой машине или в Windows-home права и защита от `uv` исчезают: вернутся
permission-промпты и риск порчи venv.

Попутно проверено: текущий allowlist полностью покрывает канонические команды AGENTS.md
(pytest/ruff/mypy/recap/recap-bridge/python.exe, cargo.exe, npm run lint/test/build), deny для
`uv` на месте; `powershell.exe`/`build-portable.ps1` в allow отсутствуют — корректно,
portable-сборка остаётся за пользователем.

## Варианты решения

1. **(Рекомендуется)** Перенести allow/deny в checked-in `.claude/settings.json` (руками
   пользователя или через `/update-config` — самостоятельная правка агентом блокируется
   классификатором, что правильно), в local оставить только личное.
2. Оставить как есть и убрать из `.gitignore` обещающий комментарий (честный минимум).

## Как проверить исправление

`git ls-files .claude/` показывает `settings.json`; в свежей сессии `uv --version` блокируется
deny-правилом, канонические команды не промптят.

## Связанные

[[AGENT-005]], [[AGENT-008]].
