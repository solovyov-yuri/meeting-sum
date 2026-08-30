---
id: AGENT-007
title: "Граница WSL-агент / Windows-only проверки (tauri, cargo) нигде не документирована"
category: AGENT
severity: medium
effort: small
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: CLAUDE.md
    anchor: "Environment & commands"
---

# AGENT-007: Недокументированная граница верификации WSL/Windows

## Проблема

В сессии `b52e3b29` пользователь вручную запускал `npm run tauri dev` в Windows PowerShell и
вставлял вывод ошибок в чат (`icons/icon.ico not found`); memory отмечает «no Rust toolchain
(cargo/rustc) in this env». CLAUDE.md ничего не говорит о том, какие проверки для `desktop/` агент
может выполнить сам, а какие требуют ручного round-trip через пользователя.

## Почему это важно

Каждое изменение, задевающее Tauri, повторно открывает эту границу заново — или (как уже было,
[[AGENT-006]]) приводит к ложному заявлению об успехе.

## Варианты решения

1. **Рекомендуется:** задокументировать в canonical-файле (или `desktop/CLAUDE.md`): из WSL доступно `npm run lint|test|build` (node.exe: `/mnt/c/Program Files/nodejs/node.exe`); НЕ доступно `tauri dev/build`, cargo — вывод этих команд пользователь вставляет из PowerShell.

## Как проверить исправление

Раздел существует; новая сессия по desktop-задаче не выясняет границу заново.

## Связанные

[[AGENT-002]], [[AGENT-006]].
