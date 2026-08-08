---
id: ARCH-004
title: "stderr моста уходит в /dev/null — технические логи, требуемые контрактом, недоступны"
category: ARCH
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: desktop/src-tauri/src/lib.rs
    anchor: ".stderr(Stdio::null())"
    line_hint: 56
  - path: src/desktop_bridge.py
    anchor: "logging.basicConfig"
    line_hint: 470
  - path: docs/desktop-bridge-contract.md
    anchor: "log tab"
    line_hint: 330
---

# ARCH-004: stderr моста отбрасывается — логов нет вообще

## Проблема

Python-мост аккуратно разделяет пользовательские сообщения (`humanize_error`) и технические
трейсбэки (`logger.exception` → stderr, `desktop_bridge.py:~462, ~510`). Rust же в обоих местах
спавна ставит `.stderr(Stdio::null())` (`lib.rs:56, 183`). Контракт (§7) обещает: «Детальные
exception strings можно хранить в log tab».

## Почему это важно

Когда реальный пользователь ловит CUDA/keyring/LLM-сбой, технической детали не существует нигде —
дебаг полевых проблем превращается в гадание. Требование контракта структурно невыполнимо.

## Варианты решения

1. **Рекомендуется (только Python):** мост сам пишет лог-файл (rotating) в каталог данных приложения (`RECAP_DESKTOP_DATA_DIR`); Rust не трогаем.
2. В Rust перенаправить stderr в файл в app-data dir (и/или `Stdio::inherit()` в dev-сборке); позже показать во вкладке «Лог».

## Как проверить исправление

Спровоцировать ошибку (неверный base_url) в десктопе → в каталоге данных появляется лог с полным трейсбэком.

## Связанные

[[ARCH-002]], [[CODE-006]] (rich-прогресс whisper тоже пишется в отбрасываемый stderr).
