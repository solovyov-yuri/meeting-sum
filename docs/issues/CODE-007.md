---
id: CODE-007
title: "api_key_configured отражает только сохранённого провайдера — ложный статус «Ключ не сохранён» для черновика"
category: CODE
severity: low
effort: small
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/desktop_bridge.py
    anchor: "_api_key_configured(sm.provider)"
    line_hint: 115
  - path: desktop/src/components/SettingsScreen.tsx
    anchor: "api_key_configured"
    line_hint: 392
---

# CODE-007: Статус ключа виден только для сохранённого провайдера

## Проблема

Ключи хранятся в keychain по-провайдерно (`secrets_store.set_api_key(provider, ...)`), но
`get_settings` отдаёт один булев `api_key_configured`, привязанный к сохранённому провайдеру.
UI показывает «Ключ не сохранён» для любого несохранённого черновика провайдера, даже если у того
есть ключ — пользователь может лишний раз ввести или ошибочно «удалить» ключи.

## Варианты решения

1. Bridge-команда `get_api_key_state(provider)` или карта `{provider: bool}` в `get_settings`; использовать в `KeysSection`.

## Как проверить исправление

Сохранить ключ для xai, переключить черновик на xai при сохранённом openai — бейдж показывает «Ключ сохранён».
