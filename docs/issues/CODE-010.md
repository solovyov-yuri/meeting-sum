---
id: CODE-010
title: "Мок bridge.ts не воспроизводит отмену запуска: после cancelRun() мок-runRecap завершается success"
category: CODE
severity: low
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: desktop/src/lib/bridge.ts
    anchor: "if (cancelled) break"
    line_hint: 335
---

# CODE-010: Mock/real расхождение в семантике отмены

## Проблема

В browser-моке `runRecap` ветка `if (cancelled) break;` лишь выходит из цикла процентов, после
чего код продолжает штатный путь: пишет транскрипт, эмитит `success` и возвращает
`status: "success"`. Реальный мост возвращает `RunResult("cancelled")`. Для `pullModel` тот же
мок отмену поддерживает корректно — расхождение локальное.

## Доказательства

`desktop/src/lib/bridge.ts` (2026-07-05): после `break` нет `cancelled`-результата.

## Почему это важно

Правило репозитория — «весь UI демонстрируется в браузере без Rust/GPU». Ветка UI для `cancelled`
(лог, `stepsForStatus`, история со статусом cancelled) в браузере недостижима, и vitest-тесты на
неё через мок не написать. Классический copy-paste-дрейф mock/real из списка рисков проекта.

## Варианты решения

1. **(Рекомендуется)** После `break` возвращать `cancelled`-результат (сохраняя
   `transcript_path`, если «этап» транскрибации успел завершиться — зеркалит семантику флага
   между этапами) и записывать его в mock-историю.

## Как проверить исправление

В браузерном демо Stop во время транскрибации даёт статус «cancelled» и запись в истории; vitest
на этот путь.

## Связанные

[[ARCH-005]] — отмена resummarize на реальной стороне.
