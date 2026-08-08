---
id: ARCH-002
title: "Отмена в десктопе: kill процесса вместо кооперативной отмены из контракта; потеря истории и указателя на транскрипт"
category: ARCH
severity: high
effort: small
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: desktop/src-tauri/src/lib.rs
    anchor: "let _ = child.kill();"
    line_hint: 199
  - path: src/desktop_bridge.py
    anchor: "result = runner(payload, emit=emit)"
    line_hint: 460
  - path: src/workflows.py
    anchor: "CancelCheck"
    line_hint: 77
  - path: docs/desktop-bridge-contract.md
    anchor: "cancellation flag"
    line_hint: 316
---

# ARCH-002: Отмена в десктопе реализована не по контракту

## Проблема

Контракт (`docs/desktop-bridge-contract.md` §6) описывает кооперативную отмену: «bridge выставляет
cancellation flag; workflow проверяет flag между этапами». Фактически:

- Python-плюмбинг отмены (`workflows.CancelCheck`, проверки `if cancelled():` на строках ~231, ~270,
  параметр `cancel=` у `run_recap`/`resummarize`) — **мёртвый код**: `_streaming` вызывает
  `runner(payload, emit=emit)` без `cancel=` (`src/desktop_bridge.py:460`).
- Rust вместо этого делает `child.kill()` (`lib.rs:199`), причём флаг проверяется только внутри
  `for line in reader.lines()` — то есть во время долгой молчаливой транскрибации (самый длинный
  этап, прогресс-строк нет) кнопка «Остановить» не действует до конца этапа.

## Почему это важно

1. Отмена после транскрибации: транскрипт уже на диске (`workflows.py:~260`), но Rust синтезирует
   результат с `"transcript_path": null` (`lib.rs:~233-241`) — пользователь теряет указатель на
   сохранённый транскрипт.
2. Убитый мост не доходит до `_record_history` — отменённый запуск исчезает из истории, хотя спека
   (§9, `docs/desktop-tauri-spec.md:~288`) явно перечисляет `cancelled` как персистентный статус.
3. `child.kill()` пропускает `finally` в `prepared_audio` — утечка временного WAV при включённом
   препроцессинге; на Windows не убивается дочерний ffmpeg (нет job object).
4. Кнопка отмены неотзывчива на самом длинном этапе.

## Варианты решения

1. **Рекомендуется:** реализовать кооперативную отмену по контракту — Rust сигнализирует (строка в stdin / sentinel-файл), мост транслирует это в `cancel`-колбэк; Python возвращает настоящий `RunResult("cancelled")` и пишет историю. Компромисс: больше IPC-плюмбинга; отмена срабатывает на границе этапа (это соответствует контракту).
2. Оставить kill, но: удалить мёртвый `CancelCheck`-плюмбинг, обновить §6 контракта и §9 спеки, писать `cancelled`-запись истории со стороны Rust, вынести проверку флага в отдельный watcher-поток (мгновенный kill), на Windows убивать дерево процессов (`taskkill /T` / job object). Компромисс: потеря указателя на транскрипт остаётся.

## Как проверить исправление

Запустить длинную транскрибацию в десктопе, нажать «Остановить» посреди этапа: запуск появляется в
истории со статусом `cancelled`; если транскрипт успел записаться — его путь доступен; в temp нет
осиротевших WAV; `ffmpeg.exe` не висит в диспетчере задач.

## Связанные

[[ARCH-004]] (та же зона lib.rs), [[DOC-001]] (обновление контракта).
