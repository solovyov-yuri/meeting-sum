# Roadmap

Живой документ. Статусы и решения здесь принадлежат человеку; повторные запуски ревью
добавляют строки и флаги, но **не** переписывают ваши решения.

Статусы: `proposed → accepted → in-progress → done`, плюс `wont-do` и `deferred`
(оба требуют причины в «Журнале решений»).

## Сводная таблица

Отсортировано по приоритету (severity × effort: дешёвые важные — выше).

| ID | Название | Severity | Effort | Статус | Отметки |
|----|----------|----------|--------|--------|---------|
| [SEC-001](issues/SEC-001.md) | Живой API-ключ в открытом виде в config.yaml | high | quick-win | done | 2026-07-02: ключ убран из config.yaml, старый ротирован, ключ через env |
| [REL-001](issues/REL-001.md) | UnicodeDecodeError не перехватывается при чтении транскрипта | high | quick-win | done | 2026-07-02: ловим (OSError, UnicodeDecodeError) в cli.py+workflows.py; тесты на оба пути |
| [REL-004](issues/REL-004.md) | Десктоп отклоняет .mp4 — реальный формат пользователя | high | quick-win | done | 2026-07-02: общая AUDIO_EXTENSIONS (+mp4/mkv/webm/flac), синк bridge.ts; drag-in-app вручную не проверял |
| [ARCH-002](issues/ARCH-002.md) | Отмена: kill вместо кооперативной; потеря истории/транскрипта | high | small | in-progress | кооперативная отмена реализована; Rust-половина не скомпилирована здесь — нужна сборка/тест |
| [AGENT-001](issues/AGENT-001.md) | Скилл project-review: нет references/assets; 3 копии | high | small | done | 2026-07-02: скилл сделан глобальным (Windows-home канонический + symlink в WSL-home), 5 файлов references/assets созданы, проектная копия удалена |
| [AGENT-002](issues/AGENT-002.md) | CLAUDE.md/AGENTS.md: desktop-слой невидим, ложное правило boundary | high | small | proposed | |
| [AGENT-006](issues/AGENT-006.md) | Ложный отчёт о верификации; правила нет в checked-in файлах | high | small | proposed | |
| [ARCH-001](issues/ARCH-001.md) | Пайплайн продублирован между cli.py и workflows.py | high | medium | proposed | |
| [ARCH-003](issues/ARCH-003.md) | output_formats — мёртвый вход контракта | medium | quick-win | proposed | |
| [ARCH-004](issues/ARCH-004.md) | stderr моста в null — логов нет | medium | quick-win | proposed | |
| [SEC-002](issues/SEC-002.md) | CSP отключён в Tauri | medium | quick-win | proposed | |
| [SEC-004](issues/SEC-004.md) | Скрытый fallback на OPENAI_API_KEY через SDK | medium | quick-win | proposed | evidence: hypothesis |
| [REL-002](issues/REL-002.md) | ffmpeg без -nostdin и timeout | medium | quick-win | proposed | |
| [REL-003](issues/REL-003.md) | Консольное окно мигает на каждый вызов моста (Windows) | medium | quick-win | proposed | evidence: hypothesis |
| [CODE-005](issues/CODE-005.md) | test_connection: черновой провайдер × сохранённый base_url | medium | quick-win | proposed | |
| [DOC-001](issues/DOC-001.md) | Контракт моста: нет test_connection/read_text/resummarize/cancel | medium | quick-win | proposed | |
| [AGENT-003](issues/AGENT-003.md) | CLAUDE.md и AGENTS.md — дубликаты байт-в-байт | medium | quick-win | proposed | после AGENT-002 |
| [AGENT-004](issues/AGENT-004.md) | /graphify недоступен из WSL (двойной .claude-home) | medium | quick-win | done | 2026-07-02: глобальный graphify удалён (осталась более свежая локальная копия в chem-app), триггер из глобального CLAUDE.md убран |
| [AGENT-005](issues/AGENT-005.md) | Allowlist не соответствует workflow; нет deny для uv | medium | quick-win | proposed | |
| [SEC-003](issues/SEC-003.md) | Нескоуплённые read_text/export_summary IPC | medium | small | proposed | |
| [CODE-001](issues/CODE-001.md) | Хардкод путей вывода рядом с аудио; перезапись {stem}.txt | medium | small | proposed | |
| [DEP-001](issues/DEP-001.md) | ESLint 8 EOL | medium | small | proposed | |
| [AGENT-007](issues/AGENT-007.md) | Граница WSL/Windows-проверок не документирована | medium | small | proposed | |
| [DEP-003](issues/DEP-003.md) | CUDA-wheels безусловные (~2 ГБ; вероятно ломают macOS) | medium | medium | proposed | |
| [PERF-001](issues/PERF-001.md) | Whisper-модель перезагружается на каждый десктоп-запуск | medium | large | proposed | |
| [CODE-002](issues/CODE-002.md) | run_one_file строит summarizer дважды | low | quick-win | proposed | |
| [CODE-003](issues/CODE-003.md) | Мёртвые transcribe_audio/summarize_transcript | low | quick-win | proposed | вместе с ARCH-001 |
| [CODE-004](issues/CODE-004.md) | Мелкий копипаст (дубликат в кортеже, no-op re-raise и др.) | low | quick-win | proposed | |
| [REL-005](issues/REL-005.md) | write_text_atomic: нет fsync; утечка tmp при сбое | low | quick-win | proposed | |
| [REL-007](issues/REL-007.md) | SSE-ошибки посреди стрима мимо retry | low | quick-win | proposed | evidence: hypothesis |
| [REL-008](issues/REL-008.md) | _ensure_output mkdir вне error boundary | low | quick-win | proposed | |
| [DEP-004](issues/DEP-004.md) | openai>=1.0 допускает несовместимый мажор | low | quick-win | proposed | |
| [CONV-001](issues/CONV-001.md) | ruff known-first-party: призраки pipeline/protocols | low | quick-win | proposed | |
| [DOC-002](issues/DOC-002.md) | README не упоминает десктоп-приложение | low | quick-win | proposed | |
| [AGENT-008](issues/AGENT-008.md) | Весь .claude/ в gitignore | low | quick-win | proposed | |
| [CODE-006](issues/CODE-006.md) | Реальный прогресс без percent (в отличие от мока) | low | small | proposed | |
| [CODE-007](issues/CODE-007.md) | Статус ключа только для сохранённого провайдера | low | small | proposed | |
| [REL-006](issues/REL-006.md) | Гонка read-modify-write в history.json | low | small | proposed | |
| [PERF-002](issues/PERF-002.md) | Чанковая суммаризация последовательная | low | medium | proposed | |
| [DEP-002](issues/DEP-002.md) | Vite/Vitest/Tailwind/React отстают на мажор(ы) | low | medium | proposed | |

## Журнал решений

<!-- Записи человека. Формат: дата — ID — решение и причина. Ревью-агент сюда только добавляет
однострочные флаги (например, «not observed in review YYYY-MM-DD — verify if resolved»)
и никогда не редактирует написанное человеком. -->

2026-07-02 — SEC-001 — in-progress. Принят вариант 1+3: секрет уходит из config.yaml в env-переменную
`RECAP_SUMMARIZATION_MODEL_API_KEY`. `config.yaml.example` переведён на подсказку про env (перестал
предлагать класть ключ в файл). Осталось: убрать строку `api_key` из локального `config.yaml` и
ротировать старый ключ на platform.openai.com. Закрыть в `done` после ротации.

2026-07-02 — SEC-001 — done. Строка `api_key` удалена из локального `config.yaml`, старый ключ
ротирован на platform.openai.com, новый ключ подаётся через `RECAP_SUMMARIZATION_MODEL_API_KEY`.

2026-07-02 — REL-001 — done. Вариант 1: чтение транскрипта ловит `(OSError, UnicodeDecodeError)` в
`cli.py summarize` и `workflows.resummarize_one`. Регрессионные тесты на cp1251 в test_cli.py и
test_workflows.py. ruff/mypy/pytest — зелёные (301 passed).

2026-07-02 — ARCH-002 — in-progress. Вариант 1 (кооперативная отмена через flag-файл): Rust
создаёт уникальный `cancel_flag` и watcher-потоком пишет его по «Остановить»; мост строит
`cancel = Path(flag).exists` и передаёт в `run_one_file`; Rust дочитывает stdout до реального
`cancelled`-результата (kill убран → `finally` в Python отрабатывает, транскрипт и запись истории
сохраняются). Добавлен UI-текст про границу этапа; §6 контракта обновлён. Python-половина покрыта
тестами (test_desktop_bridge, test_workflows), ruff/mypy/pytest — зелёные (303), фронт tsc+eslint —
чисто. НЕ проверено: компиляция Rust (нет cargo здесь) и реальная отмена в запущенном приложении.
Перевести в `done` после `cargo build` + ручной проверки «Остановить» посреди длинной транскрибации.

2026-07-02 — REL-004 — done. Вариант 1: единая константа `AUDIO_EXTENSIONS` в `workflows.py`
(+`.mp4 .mkv .webm .flac`), `cli.py` импортирует её (дубль удалён), фильтр в `bridge.ts`
синхронизирован. Юнит-тест на приём `.mp4` (run_one_file). Не проверено вручную: реальный
drag-and-drop `.mp4` в запущенном десктоп-приложении (нет GPU/Tauri-рантайма здесь).
