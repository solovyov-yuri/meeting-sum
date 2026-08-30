---
id: AGENT-011
title: "Ключевое runtime-знание (лог моста, запуск транскрибации из WSL) заперто в личной памяти; AGENTS.md утверждает обратное"
category: AGENT
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: /home/samogonn/.claude/projects/-mnt-c-Users-solov-projects-job-inno-recap/memory/recap-desktop-runtime-env.md
    anchor: "recap-bridge.log"
  - path: AGENTS.md
    anchor: "Verification boundary"
---

# AGENT-011: Институциональное знание невидимо для чужих сессий и других агентов

## Проблема

Операционные факты, добытые дорогой ценой, существуют только в auto-memory Claude Code:

- путь к логу моста, читаемому из WSL
  (`/mnt/c/Users/solov/AppData/Roaming/app.recap.desktop/logs/recap-bridge.log` — «check it
  FIRST»);
- реальная транскрибация **запускаема из WSL** (cpu/tiny через `desktop_bridge serve` +
  `RECAP_DESKTOP_DATA_DIR`) — memory прямо говорит «Contrary to the AGENTS.md caveat», тогда как
  AGENTS.md заявляет, что транскрибация не проверяема из этой среды;
- env-переменные не пересекают границу WSL→Windows; квирк NUL `isatty()=True`.

Codex-сессии, другие машины и любой свежий контекст без этой memory работают по ложной карте
среды.

## Доказательства

Файл памяти против раздела Verification boundary в AGENTS.md. Цена вопроса подтверждена историей:
баг прогресса транскрибации (сессии `427ae7bd` → `a0c2ded3`) потребовал 3+ итераций «исправлено →
не работает» именно потому, что лог моста «НИКОГДА не проверялся напрямую» (из handoff-промпта
пользователя).

## Варианты решения

1. **(Рекомендуется)** Перенести в AGENTS.md короткий подраздел «Desktop runtime debugging»:
   лог-путь первым делом; как прогнать мост из WSL (cpu/tiny); env не пересекают границу.
   Заодно снять из Verification boundary абсолют «transcription unverifiable here».
2. Отдельный `docs/desktop-debugging.md` со ссылкой из AGENTS.md.

## Как проверить исправление

`grep recap-bridge.log AGENTS.md` находит путь; вопрос «десктоп-пайплайн молчит, что смотреть
первым?» отвечается без memory.

## Связанные

[[AGENT-007]] — исходное описание границы; [[AGENT-010]] — соседний файл памяти.
