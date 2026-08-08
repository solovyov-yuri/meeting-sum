---
id: CODE-005
title: "test_connection смешивает провайдера из черновика настроек с сохранённым base_url — неверный вердикт проверки"
category: CODE
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/desktop_bridge.py
    anchor: "settings.summarization.model.base_url or PROVIDER_PRESETS.get(provider)"
    line_hint: 226
  - path: desktop/src/components/SettingsScreen.tsx
    anchor: "KeysSection"
    line_hint: 430
---

# CODE-005: test_connection даёт неверный вердикт при несохранённом провайдере

## Проблема

`test_connection(provider)` получает провайдера из **черновика** UI, а `base_url` берёт из
**последнего сохранённого** конфига (`desktop_bridge.py:~226`), который может принадлежать
другому провайдеру.

Сценарий: пользователь переключил провайдера на `openai` (не сохраняя), нажал «Проверить
подключение» → применяется сохранённый `base_url` (например, `http://localhost:11434/v1` от
ollama) → `is_external_provider` возвращает False → отчёт «Локальный провайдер». Вердикт неверен
и противоречит назначению кнопки.

## Варианты решения

1. Игнорировать сохранённый `base_url`, если переданный провайдер отличается от сохранённого (брать `PROVIDER_PRESETS[provider]`).
2. **Лучше всего соответствует намерению:** фронтенд передаёт черновой `base_url` в payload.

## Как проверить исправление

Сохранён ollama+localhost; в черновике выбрать openai и нажать проверку — вердикт про openai, не про localhost.
