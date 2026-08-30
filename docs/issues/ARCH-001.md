---
id: ARCH-001
title: "Пайплайн продублирован между cli.py и workflows.py и уже расходится в поведении"
category: ARCH
severity: high
effort: medium
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: src/cli.py
    anchor: "def run("
    line_hint: 351
  - path: src/cli.py
    anchor: "def batch("
    line_hint: 64
  - path: src/workflows.py
    anchor: "def run_one_file"
    line_hint: 174
  - path: docs/desktop-tauri-spec.md
    anchor: "тонкой командной оболочкой"
    line_hint: 87
---

# ARCH-001: Пайплайн продублирован между cli.py и workflows.py

## Проблема

Спека десктопа (`docs/desktop-tauri-spec.md` §4) требует, чтобы `cli.py` остался «тонкой командной
оболочкой», вызывающей функции из `workflows.py`. Фактически единственный импорт из workflows в CLI —
`from workflows import is_external_provider` (`src/cli.py:29`). Команды `run`, `batch`, `summarize`
заново реализуют весь конвейер transcribe → write transcript → summarize → format → write,
который целиком существует в `workflows.run_one_file`.

## Доказательства

- `cli.py` `run` (~351–443): свой `make_transcriber` + `write_text_atomic` транскрипта + `summarizer.summarize` — ни одного вызова `run_one_file`.
- Расхождения уже есть:
  - пустая транскрипция: `run` → exit code 1 (`cli.py:~423`), `batch` считает файл успешным (`cli.py:~165`), `run_one_file` возвращает статус `"failed"` (`workflows.py:~268`);
  - файлы суммари: CLI пишет один файл per `--format`, workflows всегда пишет telegram `.txt` + `.json` (`workflows.py:~327-330`).

## Почему это важно

Каждое изменение конвейера (новый шаг, новый инвариант) нужно вносить в 2–4 места; копии уже
разошлись, и различия не задокументированы как намеренные. Это главный источник будущих
«починили в десктопе — сломалось в CLI» багов.

## Варианты решения

1. **Рекомендуется:** переписать `run` (и тело цикла `batch`) через `workflows.run_one_file` с CLI-колбэком прогресса. Компромисс: русские `error_message` из `RunResult` vs английские сообщения CLI — нужен параметр языка или ключи сообщений.
2. Минимально: вынести общий хвост «summarize + format + write» (дословно повторяется в `summarize`, `run`, `batch`) в один хелпер. Меньше риска, но транскрибирующая половина остаётся продублированной.
3. Если двойная оркестрация намеренная — зафиксировать это решение в спеке и CLAUDE.md. Дешевле всего, но риск расхождения остаётся.

## Как проверить исправление

`grep -n "run_one_file" src/cli.py` находит вызовы; поведение на пустой транскрипции и набор
выходных файлов совпадают в CLI и десктопе (тесты `tests/test_cli.py`, `tests/test_workflows.py` зелёные).

## Связанные

[[CODE-003]] (мёртвые `transcribe_audio`/`summarize_transcript` логично оживить/удалить в этом же рефакторинге), [[AGENT-002]].
