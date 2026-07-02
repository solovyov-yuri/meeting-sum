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
| [AGENT-002](issues/AGENT-002.md) | CLAUDE.md/AGENTS.md: desktop-слой невидим, ложное правило boundary | high | small | done | 2026-07-02: карта +workflows/desktop_bridge/secrets_store/desktop; 3 boundary вместо ложного одного |
| [AGENT-006](issues/AGENT-006.md) | Ложный отчёт о верификации; правила нет в checked-in файлах | high | small | done | 2026-07-02: правило честной верификации добавлено в AGENTS.md |
| [ARCH-001](issues/ARCH-001.md) | Пайплайн продублирован между cli.py и workflows.py | high | medium | in-progress | 2026-07-02: опции 2+3 — общий хвост вынесен, расхождение задокументировано; полная унификация (опция 1) отложена (нужен i18n) |
| [ARCH-003](issues/ARCH-003.md) | output_formats — мёртвый вход контракта | medium | quick-win | proposed | |
| [ARCH-004](issues/ARCH-004.md) | stderr моста в null — логов нет | medium | quick-win | done | 2026-07-02: ротируемый recap-bridge.log в data dir (вариант 1, Python); тест |
| [SEC-002](issues/SEC-002.md) | CSP отключён в Tauri | medium | quick-win | in-progress | 2026-07-02: строгий CSP задан; не проверен в webview (dev+prod) |
| [SEC-004](issues/SEC-004.md) | Скрытый fallback на OPENAI_API_KEY через SDK | medium | quick-win | done | 2026-07-02: factory требует ключ для внешних провайдеров; тесты (в т.ч. с OPENAI_API_KEY в env) |
| [REL-002](issues/REL-002.md) | ffmpeg без -nostdin и timeout | medium | quick-win | done | 2026-07-02: -nostdin+DEVNULL+timeout→PreprocessingError; тесты |
| [REL-003](issues/REL-003.md) | Консольное окно мигает на каждый вызов моста (Windows) | medium | quick-win | in-progress | 2026-07-02: CREATE_NO_WINDOW в bridge_command; Rust не скомпилирован здесь |
| [CODE-005](issues/CODE-005.md) | test_connection: черновой провайдер × сохранённый base_url | medium | quick-win | proposed | |
| [DOC-001](issues/DOC-001.md) | Контракт моста: нет test_connection/read_text/resummarize/cancel | medium | quick-win | done | 2026-07-02: §4 дополнен resummarize(стрим)/test_connection/read_text; cancel — в §6 (ARCH-002) |
| [AGENT-003](issues/AGENT-003.md) | CLAUDE.md и AGENTS.md — дубликаты байт-в-байт | medium | quick-win | in-progress | 2026-07-02: AGENTS.md канонический, CLAUDE.md=@AGENTS.md; нужен взгляд в свежей сессии (импорт грузится) |
| [AGENT-004](issues/AGENT-004.md) | /graphify недоступен из WSL (двойной .claude-home) | medium | quick-win | done | 2026-07-02: глобальный graphify удалён (осталась более свежая локальная копия в chem-app), триггер из глобального CLAUDE.md убран |
| [AGENT-005](issues/AGENT-005.md) | Allowlist не соответствует workflow; нет deny для uv | medium | quick-win | proposed | нужно явное согласие (само-модификация прав) — /update-config или /fewer-permission-prompts |
| [SEC-003](issues/SEC-003.md) | Нескоуплённые read_text/export_summary IPC | medium | small | done | 2026-07-02: read_text скоуплен (history+data dir)+UnicodeDecodeError; export требует существующий каталог; тесты |
| [CODE-001](issues/CODE-001.md) | Хардкод путей вывода рядом с аудио; перезапись {stem}.txt | medium | small | proposed | |
| [DEP-001](issues/DEP-001.md) | ESLint 8 EOL | medium | small | proposed | |
| [AGENT-007](issues/AGENT-007.md) | Граница WSL/Windows-проверок не документирована | medium | small | done | 2026-07-02: раздел про WSL vs Windows-проверки в AGENTS.md |
| [DEP-003](issues/DEP-003.md) | CUDA-wheels безусловные (~2 ГБ; вероятно ломают macOS) | medium | medium | proposed | |
| [PERF-001](issues/PERF-001.md) | Whisper-модель перезагружается на каждый десктоп-запуск | medium | large | proposed | |
| [CODE-002](issues/CODE-002.md) | run_one_file строит summarizer дважды | low | quick-win | done | 2026-07-02: summarizer строится один раз и передаётся в _summarize_and_export |
| [CODE-003](issues/CODE-003.md) | Мёртвые transcribe_audio/summarize_transcript | low | quick-win | done | 2026-07-02: удалены (без вызовов); спека обновлена |
| [CODE-004](issues/CODE-004.md) | Мелкий копипаст (дубликат в кортеже, no-op re-raise и др.) | low | quick-win | done | 2026-07-02: 4 пункта — tuple, re-raise, privacy-helper, pushHistory |
| [REL-005](issues/REL-005.md) | write_text_atomic: нет fsync; утечка tmp при сбое | low | quick-win | done | 2026-07-02: flush+fsync до rename, unlink tmp при сбое write; тест |
| [REL-007](issues/REL-007.md) | SSE-ошибки посреди стрима мимо retry | low | quick-win | done | 2026-07-02: httpx.HTTPError добавлен в _RETRYABLE; тест на mid-stream |
| [REL-008](issues/REL-008.md) | _ensure_output mkdir вне error boundary | low | quick-win | done | 2026-07-02: mkdir в try/except OSError→Exit(1); тест |
| [DEP-004](issues/DEP-004.md) | openai>=1.0 допускает несовместимый мажор | low | quick-win | done | 2026-07-02: openai>=2,<3; faster-whisper<2 |
| [CONV-001](issues/CONV-001.md) | ruff known-first-party: призраки pipeline/protocols | low | quick-win | done | 2026-07-02: убраны pipeline/protocols, добавлен preprocessing |
| [DOC-002](issues/DOC-002.md) | README не упоминает десктоп-приложение | low | quick-win | done | 2026-07-02: секция «Десктоп-приложение» со ссылками |
| [AGENT-008](issues/AGENT-008.md) | Весь .claude/ в gitignore | low | quick-win | done | 2026-07-02: ignore сужен до settings.local.json |
| [CODE-006](issues/CODE-006.md) | Реальный прогресс без percent (в отличие от мока) | low | small | proposed | |
| [CODE-007](issues/CODE-007.md) | Статус ключа только для сохранённого провайдера | low | small | proposed | |
| [REL-006](issues/REL-006.md) | Гонка read-modify-write в history.json | low | small | done | 2026-07-02: файловый лок (msvcrt/fcntl) вокруг append/delete; тест |
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

2026-07-02 — Wave 2 (parallel субагенты, disjoint-файлы) — done: SEC-004 (factory требует ключ для
внешних провайдеров), DEP-004 (major-cap openai/faster-whisper), AGENT-002/006/007 (карта, boundary,
честная верификация, WSL/Windows-граница в AGENTS.md). AGENT-003 — in-progress: CLAUDE.md сведён к
`@AGENTS.md`; синтаксис импорта подтверждён по докам, но фактическая загрузка проверяется только в
свежей сессии — нужен один взгляд пользователя. AGENT-005 — не сделано: правка allowlist в
`.claude/settings.local.json` заблокирована классификатором как само-модификация прав; сделать через
`/update-config` или `/fewer-permission-prompts` с явного согласия. pytest 310, ruff/mypy — зелёные.

2026-07-02 — ARCH-001 — in-progress. Приняты варианты 2+3: общий хвост summarize→format→write в
`cli.py` вынесен в `_summarize_or_exit`/`_format_summary`; расхождение CLI↔desktop (язык сообщений,
один файл на --format vs .txt+.json) задокументировано в spec §4 и AGENTS.md как намеренное. Заодно
CODE-002/003/004 закрыты. Полная унификация CLI через `run_one_file` (вариант 1) отложена — требует
i18n сообщений и смены семантики выходных файлов CLI (решение владельца). Открытый под-вопрос: пустая
транскрипция трактуется по-разному в `batch` (успех) vs `run`/`run_one_file` (ошибка) — унификация
изменит поведение `batch`. pytest 310, ruff/mypy зелёные, фронт tsc+eslint чисто, CLI-путь summarize
проверен вживую (чистая ошибка LLM + exit 1).
