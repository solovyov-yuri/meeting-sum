# Roadmap

Живой документ. Статусы и решения здесь принадлежат человеку; повторные запуски ревью
добавляют строки и флаги, но **не** переписывают ваши решения.

Статусы: `proposed → accepted → in-progress → done`, плюс `wont-do` и `deferred`
(оба требуют причины в «Журнале решений»).

## Сводная таблица

Отсортировано по приоритету (severity × effort: дешёвые важные — выше).

| ID | Название | Severity | Effort | Статус | Отметки |
|----|----------|----------|--------|--------|---------|
| [SEC-005](issues/SEC-005.md) | Тесты не изолированы от RECAP_*-env: сьют красный, живой ключ в выводе pytest | high | quick-win | proposed | ревью 2026-07-05; ключ засвечен в логах — ротировать |
| [AGENT-009](issues/AGENT-009.md) | AGENTS.md ложен: запрещает существующую унификацию CLI↔workflows, карта без 2 модулей | high | quick-win | proposed | ревью 2026-07-05; рецидив AGENT-002 |
| [ARCH-006](issues/ARCH-006.md) | Round-trip render↔parse не точен: \n в элементе списка портит блоки при save/export | medium | quick-win | proposed | ревью 2026-07-05; воспроизведено скриптом |
| [CODE-008](issues/CODE-008.md) | Регрессия: da9d474 удалил duration-probe из 3dd5381 — прогресс молчит при duration=0 | medium | quick-win | proposed | ревью 2026-07-05; реальный вход пользователя |
| [REL-009](issues/REL-009.md) | Ollama pull: timeout=None — вечное зависание, cancel не срабатывает | medium | quick-win | proposed | ревью 2026-07-05 |
| [SEC-006](issues/SEC-006.md) | CUDA-wheels скачиваются без проверки sha256 | medium | quick-win | proposed | ревью 2026-07-05 |
| [AGENT-010](issues/AGENT-010.md) | Память desktop-tauri-mvp.md противоречит текущей архитектуре | medium | quick-win | proposed | ревью 2026-07-05 |
| [AGENT-011](issues/AGENT-011.md) | Runtime-знание (лог моста, запуск из WSL) заперто в памяти; AGENTS.md утверждает обратное | medium | quick-win | proposed | ревью 2026-07-05 |
| [AGENT-012](issues/AGENT-012.md) | desktop-agent-checklist.md — завершённое ТЗ под видом живого чеклиста | medium | quick-win | proposed | ревью 2026-07-05 |
| [ARCH-005](issues/ARCH-005.md) | resummarize игнорирует cancel_flag — «Остановить» не работает в режимах суммаризации | medium | small | proposed | ревью 2026-07-05 |
| [REL-010](issues/REL-010.md) | _ensure_cuda не смотрит на реальное GPU: без NVIDIA ~2 ГБ впустую + падение; auto — тихий CPU | medium | small | proposed | ревью 2026-07-05; auto-часть — hypothesis |
| [SEC-007](issues/SEC-007.md) | save_summary/export_summary: нескоуплённая запись из webview (traversal через base_name) | medium | small | proposed | ревью 2026-07-05; асимметрия с SEC-003 |
| [DOC-003](issues/DOC-003.md) | Контракт моста снова отстал: нет download-шага и 3 команд | medium | small | proposed | ревью 2026-07-05; рецидив DOC-001 |
| [DOC-004](issues/DOC-004.md) | README/CLI-help/spec не знают про lecture, новые расширения, portable | medium | small | proposed | ревью 2026-07-05 |
| [AGENT-013](issues/AGENT-013.md) | Долг ручной Windows-QA нигде не накапливается | medium | small | proposed | ревью 2026-07-05 |
| [SEC-008](issues/SEC-008.md) | Zip-slip в _extract_dlls | low | quick-win | proposed | ревью 2026-07-05; фиксить вместе с SEC-006 |
| [SEC-009](issues/SEC-009.md) | pull_model доверяет base_url из webview (SSRF) | low | quick-win | proposed | ревью 2026-07-05 |
| [REL-011](issues/REL-011.md) | Портативный ffmpeg.exe не находится мостом без ручного PATH | low | quick-win | proposed | ревью 2026-07-05 |
| [REL-012](issues/REL-012.md) | _force_utf8_io не переконфигурирует stdin | low | quick-win | proposed | ревью 2026-07-05 |
| [REL-013](issues/REL-013.md) | export_summary падает целиком на битом .json вместо фолбэка на Markdown | low | quick-win | proposed | ревью 2026-07-05 |
| [CODE-009](issues/CODE-009.md) | SUMMARY_JSON_SCHEMA — мёртвый код (реально шлётся только json_object) | low | quick-win | proposed | ревью 2026-07-05 |
| [CODE-010](issues/CODE-010.md) | Мок bridge.ts: после cancelRun запуск всё равно success | low | quick-win | proposed | ревью 2026-07-05 |
| [CODE-011](issues/CODE-011.md) | serve() дублирует стриминг-обвязку _streaming() | low | quick-win | proposed | ревью 2026-07-05 |
| [PERF-003](issues/PERF-003.md) | Распаковка CUDA: DLL целиком в память, cancel не опрашивается | low | quick-win | proposed | ревью 2026-07-05 |
| [DEP-005](issues/DEP-005.md) | Пины CUDA: pyproject >= vs cuda_support == — дрейф при обновлении lock | low | quick-win | proposed | ревью 2026-07-05 |
| [DEP-006](issues/DEP-006.md) | PyInstaller не задекларирован и не запинен | low | quick-win | proposed | ревью 2026-07-05 |
| [CONV-002](issues/CONV-002.md) | ruff known-first-party отстал снова (3 новых модуля) — удалить список | low | quick-win | proposed | ревью 2026-07-05; рецидив CONV-001 |
| [DOC-005](issues/DOC-005.md) | Доковая пыль: шапка spec противоречит телу; «338 tests»; step-комментарий | low | quick-win | proposed | ревью 2026-07-05 |
| [AGENT-014](issues/AGENT-014.md) | Allowlist только в settings.local.json; общий settings.json не создан | low | quick-win | proposed | ревью 2026-07-05 |
| [AGENT-015](issues/AGENT-015.md) | Относительные allow-паттерны могут не покрывать составные вызовы | low | quick-win | proposed | ревью 2026-07-05; hypothesis |
| [REL-014](issues/REL-014.md) | Ротация recap-bridge.log ломается при живом worker (Windows) | low | small | proposed | ревью 2026-07-05; hypothesis |
| [CODE-012](issues/CODE-012.md) | stepsForStatus красит не те шаги для не-full режимов истории | low | small | proposed | ревью 2026-07-05; hypothesis |
| [SEC-001](issues/SEC-001.md) | Живой API-ключ в открытом виде в config.yaml | high | quick-win | done | 2026-07-02: ключ убран из config.yaml, старый ротирован, ключ через env |
| [REL-001](issues/REL-001.md) | UnicodeDecodeError не перехватывается при чтении транскрипта | high | quick-win | done | 2026-07-02: ловим (OSError, UnicodeDecodeError) в cli.py+workflows.py; тесты на оба пути |
| [REL-004](issues/REL-004.md) | Десктоп отклоняет .mp4 — реальный формат пользователя | high | quick-win | done | 2026-07-02: общая AUDIO_EXTENSIONS (+mp4/mkv/webm/flac), синк bridge.ts; drag-in-app вручную не проверял |
| [ARCH-002](issues/ARCH-002.md) | Отмена: kill вместо кооперативной; потеря истории/транскрипта | high | small | done | 2026-07-02: кооперативная отмена; пользователь подтвердил в app (сообщение про границу этапа, cancelled в истории) |
| [AGENT-001](issues/AGENT-001.md) | Скилл project-review: нет references/assets; 3 копии | high | small | done | 2026-07-02: скилл сделан глобальным (Windows-home канонический + symlink в WSL-home), 5 файлов references/assets созданы, проектная копия удалена |
| [AGENT-002](issues/AGENT-002.md) | CLAUDE.md/AGENTS.md: desktop-слой невидим, ложное правило boundary | high | small | done | 2026-07-02: карта +workflows/desktop_bridge/secrets_store/desktop; 3 boundary вместо ложного одного |
| [AGENT-006](issues/AGENT-006.md) | Ложный отчёт о верификации; правила нет в checked-in файлах | high | small | done | 2026-07-02: правило честной верификации добавлено в AGENTS.md |
| [ARCH-001](issues/ARCH-001.md) | Пайплайн продублирован между cli.py и workflows.py | high | medium | done | 2026-07-02: CLI полностью через workflows (run/batch/summarize); сообщения RU, всегда .txt+.json, empty=fail; -f json (stdout) сохранён; ~20 тестов, реальный запуск |
| [ARCH-003](issues/ARCH-003.md) | output_formats — мёртвый вход контракта | medium | quick-win | done | 2026-07-02: output_format/output_formats удалены из RunOptions, моста, фронта, контракта |
| [ARCH-004](issues/ARCH-004.md) | stderr моста в null — логов нет | medium | quick-win | done | 2026-07-02: ротируемый recap-bridge.log в data dir (вариант 1, Python); тест |
| [SEC-002](issues/SEC-002.md) | CSP отключён в Tauri | medium | quick-win | done | 2026-07-02: строгий CSP; пользователь подтвердил — работает |
| [SEC-004](issues/SEC-004.md) | Скрытый fallback на OPENAI_API_KEY через SDK | medium | quick-win | done | 2026-07-02: factory требует ключ для внешних провайдеров; тесты (в т.ч. с OPENAI_API_KEY в env) |
| [REL-002](issues/REL-002.md) | ffmpeg без -nostdin и timeout | medium | quick-win | done | 2026-07-02: -nostdin+DEVNULL+timeout→PreprocessingError; тесты |
| [REL-003](issues/REL-003.md) | Консольное окно мигает на каждый вызов моста (Windows) | medium | quick-win | done | 2026-07-02: CREATE_NO_WINDOW; пользователь подтвердил — консоль не мигает |
| [CODE-005](issues/CODE-005.md) | test_connection: черновой провайдер × сохранённый base_url | medium | quick-win | done | 2026-07-02: saved base_url только если провайдер совпадает, иначе preset; тест |
| [DOC-001](issues/DOC-001.md) | Контракт моста: нет test_connection/read_text/resummarize/cancel | medium | quick-win | done | 2026-07-02: §4 дополнен resummarize(стрим)/test_connection/read_text; cancel — в §6 (ARCH-002) |
| [AGENT-003](issues/AGENT-003.md) | CLAUDE.md и AGENTS.md — дубликаты байт-в-байт | medium | quick-win | done | 2026-07-02: пользователь подтвердил — @AGENTS.md импорт грузится в свежей сессии |
| [AGENT-004](issues/AGENT-004.md) | /graphify недоступен из WSL (двойной .claude-home) | medium | quick-win | done | 2026-07-02: глобальный graphify удалён (осталась более свежая локальная копия в chem-app), триггер из глобального CLAUDE.md убран |
| [AGENT-005](issues/AGENT-005.md) | Allowlist не соответствует workflow; нет deny для uv | medium | quick-win | done | 2026-07-02: allowlist применён через /update-config; deny Bash(uv *) добавлен |
| [SEC-003](issues/SEC-003.md) | Нескоуплённые read_text/export_summary IPC | medium | small | done | 2026-07-02: read_text скоуплен (history+data dir)+UnicodeDecodeError; export требует существующий каталог; тесты |
| [CODE-001](issues/CODE-001.md) | Хардкод путей вывода рядом с аудио; перезапись {stem}.txt | medium | small | done | 2026-07-02: run honors configured paths (Пути-экран); tsc/eslint. Остаток: overwrite при пустых путях — follow-up. Не гонял app |
| [DEP-001](issues/DEP-001.md) | ESLint 8 EOL | medium | small | done | 2026-07-02: flat config eslint.config.mjs, eslint^9; lint/build/test зелёные (npm из WSL) |
| [AGENT-007](issues/AGENT-007.md) | Граница WSL/Windows-проверок не документирована | medium | small | done | 2026-07-02: раздел про WSL vs Windows-проверки в AGENTS.md |
| [DEP-003](issues/DEP-003.md) | CUDA-wheels безусловные (~2 ГБ; вероятно ломают macOS) | medium | medium | done | 2026-07-02: маркеры sys_platform!=darwin; пользователь прогнал uv lock |
| [PERF-001](issues/PERF-001.md) | Whisper-модель перезагружается на каждый десктоп-запуск | medium | large | done | 2026-07-02: persistent worker + warm-cache + fallback; пользователь подтвердил — ок |
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
| [CODE-006](issues/CODE-006.md) | Реальный прогресс без percent (в отличие от мока) | low | small | done | 2026-07-02: on_progress в WhisperTranscriber, run_one_file шлёт percent посегментно; тест. Живой бар видно только на GPU |
| [CODE-007](issues/CODE-007.md) | Статус ключа только для сохранённого провайдера | low | small | done | 2026-07-02: api_keys_configured{provider:bool} в get_settings; UI по черновому провайдеру; тесты+tsc |
| [REL-006](issues/REL-006.md) | Гонка read-modify-write в history.json | low | small | done | 2026-07-02: файловый лок (msvcrt/fcntl) вокруг append/delete; тест |
| [PERF-002](issues/PERF-002.md) | Чанковая суммаризация последовательная | low | medium | done | 2026-07-02: ThreadPoolExecutor(3) для чанков только на внешних провайдерах (localhost — последовательно), порядок сохранён; тесты |
| [DEP-002](issues/DEP-002.md) | Vite/Vitest/Tailwind/React отстают на мажор(ы) | low | medium | done | 2026-07-02: vite^7+vitest^3+react^19+tailwind^4; build/lint/test зелёные. TW4 — нужен визуальный обзор (границы/фокус/тени) |

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

2026-07-02 — Rust verifiability — исправлено заблуждение: Windows `cargo.exe` доступен из WSL
(`/mnt/c/Users/solov/.cargo/bin/cargo.exe`). `cargo check`+`clippy` на desktop/src-tauri проходят чисто
(~5с, deps в target/). ARCH-002/REL-003: компиляция Rust ПРОВЕРЕНА здесь; непроверенным остаётся только
поведение в запущенном app. AGENTS.md (граница проверок) исправлен; 2 пред-существующих clippy-варнинга убраны.

2026-07-02 — PERF-001 — in-progress. Опция 1 (долгоживущий воркер), scoped: только run_recap идёт
через persistent `recap-bridge serve` (тёплая Whisper-модель, кэш на 1 модель по полям
transcription.model, drop старой перед новой). Serial через Mutex; чтение до терминальной строки
(stdout не EOF-ится); watcher/flag отмены переиспользованы из ARCH-002; воркер убивается на Exit.
ОБЯЗАТЕЛЬНЫЙ fallback: сломанный/незапустившийся воркер → свежий spawn-per-call (медленно, но
корректно). resummarize не трогали (LLM-only). Проверено здесь: Python 320 тестов (в т.ч.
make_transcriber 1× на 2 запуска), ruff/mypy, cargo check+clippy чисто. НЕ проверено: реальное
тёплое переиспользование модели и жизненный цикл воркера в запущенном app на GPU — за пользователем.

2026-07-02 — DEP-001/002/003. Обнаружено: фронт-тулчейн запускается из WSL через Windows-node
(`/mnt/c/Program Files/nodejs`), так что npm install/lint/build/test здесь ПРОВЕРЯЕМЫ (раньше считал иначе).
DEP-001 done: миграция на ESLint 9 flat config (eslint.config.mjs), lint 0 ошибок, build+vitest зелёные.
DEP-002 in-progress: vite^7+vitest^3+plugin-react^5 — build (tsc+vite) и 7 тестов зелёные; Tailwind 4 и
React 19 сознательно оставлены отдельными миграциями (по рекомендации issue). DEP-003 in-progress:
env-маркеры на CUDA-wheels — за пользователем `uv lock` (uv из WSL запрещён) и проверка резолва на macOS.

2026-07-02 — CODE-006/PERF-002 — done. CODE-006: посегментный percent из WhisperTranscriber через
run_one_file (CLI-путь не трогали — расхождение ARCH-001). PERF-002: параллельные чанки на внешних
провайдерах (гейт по localhost), порядок через executor.map, merge последовательный.
2026-07-02 — DEP-002 — React 19 добавлен (build/test зелёные). Tailwind 4 отложен ОСОЗНАННО: у TW4
несколько ломающих дефолтов, задевающих этот код (bare `border`, `outline-none`, `shadow`, ring), а
визуальную корректность отсюда проверить нельзя. TW3 поддерживается, issue = low. Делать только с твоим
визуальным ревью запущенного app.
2026-07-02 — AGENT-005 — заблокировано классификатором (само-модификация прав) даже при явной просьбе
«доделать всё»: правку allowlist нужно делать вне auto-mode / через /update-config. Готовый JSON выдан.

2026-07-02 — ARCH-001 — done (решение пользователя: унифицировать, расхождения не нужны). CLI run/batch/
summarize идут через run_one_file/resummarize_one. Последствия (приняты): русские сообщения пайплайна
(валидация провайдера/режима остаётся английской из фабрики), CLI всегда пишет .txt+.json, пустая
транскрипция теперь fail и в batch. Сохранено: summarize -f json пишет оба файла, а в stdout отдаёт .json
(пайпинг не потерян). batch переиспользует модель через transcriber_factory. Реальный recap.exe проверен.
2026-07-02 — ARCH-003 — done. Мёртвое поле удалено везде (после ARCH-001 оно мёртво и в CLI).
2026-07-02 — DEP-002 — done. Tailwind 4 мигрирован (@import+@config, компат-шимы для border/shadow).
Собирается/линт/тесты зелёные, но ВИЗУАЛЬНО не проверено (headless) — пользователь смотрит границы,
focus-ring (v4 outline-none/ring), тени в запущенном app.

2026-07-02 — финал. Все 40 issue закрыты. AGENT-003 (импорт подтверждён), AGENT-005 (allowlist через
/update-config + deny uv), DEP-003 (uv lock выполнен пользователем). Tailwind 4 ждёт визуального обзора
в запущенном app (сборка/тесты зелёные), но реализация закрыта.
