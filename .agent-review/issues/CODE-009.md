---
id: CODE-009
title: "SUMMARY_JSON_SCHEMA — мёртвый код: докстринг обещает response_format=json_schema, реально используется только json_object"
category: CODE
severity: low
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/summary_schema.py
    anchor: "SUMMARY_JSON_SCHEMA"
    line_hint: 31
  - path: src/providers/llm.py
    anchor: '{"type": "json_object"}'
    line_hint: 180
---

# CODE-009: Схема саммари объявлена, но никуда не передаётся

## Проблема

`summary_schema.SUMMARY_JSON_SCHEMA` (~60 строк) документирована как схема для
`response_format={"type": "json_schema", ...}`, но `llm.py` строит только
`response_format = {"type": "json_object"} if structured else None`; grep по проекту показывает,
что единственное вхождение константы — её определение. Структуру выхода фактически контролирует
только промпт; читатель (и следующий агент) ошибочно полагает, что schema-enforcement есть.

## Доказательства

`grep -rn SUMMARY_JSON_SCHEMA src/` → одно определение (2026-07-05); `providers/llm.py` — только
`json_object`.

## Почему это важно

Мёртвый код с вводящим в заблуждение докстрингом; при этом реальное подключение схемы дало бы
меньше фолбэков на текстовый путь (меньше расхождений структуры).

## Варианты решения

1. **(Рекомендуется)** Прокинуть схему:
   `response_format={"type":"json_schema","json_schema":{"name":"meeting_summary","schema":SUMMARY_JSON_SCHEMA}}`
   с фолбэком на `json_object`/текстовый путь при отказе провайдера — механизм фолбэка в
   `_generate_summary` уже есть.
2. Либо удалить константу и поправить докстринг модуля (честный минимум).

## Как проверить исправление

Unit-тест на состав `response_format` в финальном вызове; structured-путь на Ollama/OpenAI не
ломается (фолбэк остаётся).
