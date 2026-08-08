---
id: AGENT-003
title: "CLAUDE.md и AGENTS.md — дубликаты байт-в-байт: двойное сопровождение, синхронное устаревание"
category: AGENT
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: [AGENT-002]
locations:
  - path: CLAUDE.md
    anchor: "# CLAUDE.md"
    line_hint: 1
  - path: AGENTS.md
    anchor: "# AGENTS.md"
    line_hint: 1
---

# AGENT-003: Дублирование CLAUDE.md/AGENTS.md

## Проблема

`diff CLAUDE.md AGENTS.md` отличается только строками 1 и 3 (заголовок и «Claude Code» vs
«Codex») — проверено. Оба 5.8K, оба от 18 июня, оба устарели вместе ([[AGENT-002]]) — режим отказа
«обновить в двух местах» уже сработал.

## Почему это важно

Каждая правка документации — дважды; молчаливый дрейф даст Claude и Codex разные правила.

## Варианты решения

1. **Рекомендуется:** сделать AGENTS.md каноническим, CLAUDE.md сократить до `@AGENTS.md` + Claude-специфичные заметки (Claude Code поддерживает импорты `@file`).
2. Наоборот (CLAUDE.md канонический) — если Codex поддерживает аналогичное включение.

## Как проверить исправление

Один файл с содержимым; второй — однострочный импорт/ссылка. Правки вносятся в одно место.
