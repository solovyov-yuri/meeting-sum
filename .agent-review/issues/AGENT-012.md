---
id: AGENT-012
title: "docs/desktop-agent-checklist.md — завершённое одноразовое ТЗ, на которое AGENTS.md ссылается как на живой чеклист верификации"
category: AGENT
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: docs/desktop-agent-checklist.md
    anchor: "checklist"
  - path: AGENTS.md
    anchor: "desktop-agent-checklist"
---

# AGENT-012: Ссылка honesty-правила ведёт на исторический артефакт

## Проблема

AGENTS.md подкрепляет правило честной верификации ссылкой «See
docs/desktop-agent-checklist.md». Но документ (не менялся с 2026-06-19) — это ТЗ уже выполненной
работы: §2–3 инструктируют «вынести reusable workflow из cli.py», «создать Tauri app»; список
форматов экспорта в §5 («Telegram/plain/JSON») устарел после structured-пайплайна 04.07
(markdown/plain/html/json). К honesty-правилу относится только последняя строка (§6). Агент,
добросовестно прочитавший документ по ссылке, получает устаревшую картину.

## Варианты решения

1. **(Рекомендуется)** Урезать до живого чеклиста «перед сдачей desktop-изменения»: обновлённый
   Manual QA (§5) + §6 + правило о невыполнимых из WSL проверках; сюда же органично ложится
   [[AGENT-013]] (учёт долга ручной QA).
2. Пометить как исторический артефакт MVP и убрать ссылку из AGENTS.md.

## Как проверить исправление

Документ не содержит императивов о создании уже существующего; форматы экспорта совпадают с
`formatters.py`; ссылка из AGENTS.md ведёт на актуальный текст.

## Связанные

[[AGENT-013]], [[AGENT-006]] — происхождение honesty-правила.
