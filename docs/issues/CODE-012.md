---
id: CODE-012
title: "stepsForStatus при открытии истории красит не те шаги для не-full режимов: упавший summarize-запуск выглядит нетронутым"
category: CODE
severity: low
effort: small
status: proposed
evidence: hypothesis
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: desktop/src/hooks/useRecap.ts
    anchor: "stepsForStatus"
    line_hint: 85
  - path: desktop/src/components/Workspace.tsx
    anchor: "visibleSteps"
    line_hint: 85
---

# CODE-012: Раскраска шагов истории игнорирует run_mode

## Проблема

При открытии записи истории `setSteps(stepsForStatus(item.status))`: для `failed` ошибка всегда
ставится на шаг `transcribe`, для `partial_success` — на `summarize`. Но какие кольца видимы,
решает `run_mode` (`visibleSteps`). Для записи `run_mode: "summarize"` со статусом `failed`
(например, пустой транскрипт в `resummarize_one`) видимое кольцо — только `summarize`, а ошибка
уходит на невидимый `transcribe`: переоткрытый упавший запуск выглядит как «ничего не делали».
Аналогично `preprocess`-режим с `failed`.

Логика подтверждена чтением кода; фактический рендер в браузере/приложении не проверялся — потому
`evidence: hypothesis`. Подтвердит vitest на `openHistoryItem` или взгляд в браузерное демо.

## Почему это важно

История — основной способ вернуться к прошлым запускам; упавший запуск без видимой ошибки
провоцирует «повторить и снова ждать».

## Варианты решения

1. **(Рекомендуется)** Передавать в `stepsForStatus` ещё и `run_mode`, ставя терминальный статус
   на последний шаг из `MODE_STEPS[runMode]`.

## Как проверить исправление

Vitest: `openHistoryItem` с `run_mode: "summarize", status: "failed"` →
`steps.summarize.status === "error"`; визуально в браузерном демо.
