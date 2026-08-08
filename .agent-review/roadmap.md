# Roadmap

Живой документ. Статусы и решения здесь принадлежат человеку; повторные запуски ревью
добавляют строки и флаги, но **не** переписывают ваши решения.

Статусы: `proposed → accepted → in-progress → done`, плюс `wont-do` и `deferred`
(оба требуют причины в «Журнале решений»).

## Сводная таблица

Отсортировано по приоритету (severity × effort: дешёвые важные — выше).

| ID | Название | Severity | Effort | Статус | Отметки |
|----|----------|----------|--------|--------|---------|
| [SEC-005](issues/SEC-005.md) | Тесты не изолированы от RECAP_*-env: сьют красный, живой ключ в выводе pytest | high | quick-win | done | 2026-08-08: conftest-скраббер (коммит 783bd55), сьют зелёный; ключ ротирован |
| [AGENT-009](issues/AGENT-009.md) | AGENTS.md ложен: запрещает существующую унификацию CLI↔workflows, карта без 2 модулей | high | quick-win | done | 2026-08-08: п.1 устарел (0ac5799), карта +2 модуля, lecture, правило про доки |
| [ARCH-006](issues/ARCH-006.md) | Round-trip render↔parse не точен: \n в элементе списка портит блоки при save/export | medium | quick-win | done | 2026-08-08: нормализация в summary_schema (вариант 1) + 4 теста |
| [ARCH-007](issues/ARCH-007.md) | parse_plain: CAPS-метка списка читается как заголовок, проза с двоеточием — как метка | medium | quick-win | done | 2026-08-08: разделение по пустой строке (вариант 1); найдена и починена третья форма |
| [CODE-008](issues/CODE-008.md) | Регрессия: da9d474 удалил duration-probe из 3dd5381 — прогресс молчит при duration=0 | medium | quick-win | wont-do | 2026-08-08: не дефект — посылка issue опровергнута логом и текстом da9d474 |
| [REL-009](issues/REL-009.md) | Ollama pull: timeout=None — вечное зависание, cancel не срабатывает | medium | quick-win | done | 2026-08-08: PULL_IDLE_TIMEOUT на чтение + cancel на выходе из таймаута |
| [SEC-006](issues/SEC-006.md) | CUDA-wheels скачиваются без проверки sha256 | medium | quick-win | done | 2026-08-08: потоковый sha256 против digests PyPI, до распаковки |
| [AGENT-010](issues/AGENT-010.md) | Память desktop-tauri-mvp.md противоречит текущей архитектуре | medium | quick-win | done | 2026-08-08: файл переписан (вариант 1), 4 ложных утверждения убраны |
| [AGENT-011](issues/AGENT-011.md) | Runtime-знание (лог моста, запуск из WSL) заперто в памяти; AGENTS.md утверждает обратное | medium | quick-win | done | 2026-08-08: раздел «Desktop runtime debugging» в AGENTS.md; память ужата до ссылки |
| [AGENT-012](issues/AGENT-012.md) | desktop-agent-checklist.md — завершённое ТЗ под видом живого чеклиста | medium | quick-win | done | 2026-08-08: переписан как чеклист перед сдачей (вариант 1) |
| [ARCH-005](issues/ARCH-005.md) | resummarize игнорирует cancel_flag — «Остановить» не работает в режимах суммаризации | medium | small | done | 2026-08-08: cancel проброшен в resummarize_one + опрос после ответа LLM; в app не проверено |
| [REL-010](issues/REL-010.md) | _ensure_cuda не смотрит на реальное GPU: без NVIDIA ~2 ГБ впустую + падение; auto — тихий CPU | medium | small | done | 2026-08-08: детекция через драйвер (ctypes) до загрузки; ветка «нет карты» проверена только моками |
| [SEC-007](issues/SEC-007.md) | save_summary/export_summary: нескоуплённая запись из webview (traversal через base_name) | medium | small | done | 2026-08-08: запись скоуплена по истории, base_name — только имя файла |
| [DOC-003](issues/DOC-003.md) | Контракт моста снова отстал: нет download-шага и 3 команд | medium | small | done | 2026-08-08: check_model/pull_model добавлены, пример get_settings обновлён; download-шаг и save_summary закрыты попутно |
| [DOC-004](issues/DOC-004.md) | README/CLI-help/spec не знают про lecture, новые расширения, portable | medium | small | done | 2026-08-08: lecture в --help/README/spec, 8 расширений, ссылка на portable-build |
| [AGENT-013](issues/AGENT-013.md) | Долг ручной Windows-QA нигде не накапливается | medium | small | done | 2026-08-08: docs/manual-qa-pending.md + правило в AGENTS.md; засеян долгом этого прогона |
| [SEC-008](issues/SEC-008.md) | Zip-slip в _extract_dlls | low | quick-win | done | 2026-08-08: валидация имени члена до создания файлов; PoC на pre-fix коде подтвердил побег |
| [SEC-009](issues/SEC-009.md) | pull_model доверяет base_url из webview (SSRF) | low | quick-win | done | 2026-08-08: base_url/model резолвятся из настроек, как в check_model; payload игнорируется |
| [REL-011](issues/REL-011.md) | Портативный ffmpeg.exe не находится мостом без ручного PATH | low | quick-win | done | 2026-08-08: поиск на стороне Python (вариант 2) — Rust не трогали, покрыто тестами |
| [REL-012](issues/REL-012.md) | _force_utf8_io не переконфигурирует stdin | low | quick-win | done | 2026-08-08: stdin в том же цикле + тест на cp1251-поток |
| [REL-013](issues/REL-013.md) | export_summary падает целиком на битом .json вместо фолбэка на Markdown | low | quick-win | done | 2026-08-08: фолбэк на текст + отказ до записи, если пусты оба источника |
| [CODE-009](issues/CODE-009.md) | SUMMARY_JSON_SCHEMA — мёртвый код (реально шлётся только json_object) | low | quick-win | done | 2026-08-08: схема прокинута (вариант 1), деградация json_schema → json_object → текст |
| [CODE-010](issues/CODE-010.md) | Мок bridge.ts: после cancelRun запуск всё равно success | low | quick-win | done | 2026-08-08: cancelled-результат в runRecap и resummarize мока + vitest |
| [CODE-011](issues/CODE-011.md) | serve() дублирует стриминг-обвязку _streaming() | low | quick-win | done | 2026-08-08: serve() зовёт _streaming() с transcriber_factory; framing и отмена — общие |
| [PERF-003](issues/PERF-003.md) | Распаковка CUDA: DLL целиком в память, cancel не опрашивается | low | quick-win | done | 2026-08-08: copyfileobj + опрос cancel между членами (тот же коммит, что SEC-008) |
| [DEP-005](issues/DEP-005.md) | Пины CUDA: pyproject >= vs cuda_support == — дрейф при обновлении lock | low | quick-win | done | 2026-08-08: тест сверки CUDA_PACKAGES с uv.lock (вариант 1) |
| [DEP-006](issues/DEP-006.md) | PyInstaller не задекларирован и не запинен | low | quick-win | done | 2026-08-08: группа packaging = pyinstaller>=6,<7; скрипт через uv sync --group packaging |
| [CONV-002](issues/CONV-002.md) | ruff known-first-party отстал снова (3 новых модуля) — удалить список | low | quick-win | done | 2026-08-08: список удалён (вариант 1), автодетект по src = ["src"] |
| [DOC-005](issues/DOC-005.md) | Доковая пыль: шапка spec противоречит телу; «338 tests»; step-комментарий | low | quick-win | done | 2026-08-08: все три пункта |
| [AGENT-014](issues/AGENT-014.md) | Allowlist только в settings.local.json; общий settings.json не создан | low | quick-win | done | 2026-08-08: вариант 2 по решению владельца — .gitignore больше не обещает общий settings.json |
| [AGENT-015](issues/AGENT-015.md) | Относительные allow-паттерны могут не покрывать составные вызовы | low | quick-win | wont-do | 2026-08-08: рекомендованный вариант — наблюдать; за прогон промптов на канонических командах не было |
| [REL-014](issues/REL-014.md) | Ротация recap-bridge.log ломается при живом worker (Windows) | low | small | done | 2026-08-08: гипотеза подтверждена (WinError 32 на rename), воркер пишет в отдельный файл |
| [CODE-012](issues/CODE-012.md) | stepsForStatus красит не те шаги для не-full режимов истории | low | small | done | 2026-08-08: гипотеза подтверждена (fail-first тест), статус кладётся на видимый шаг режима |
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

2026-08-08 — SEC-005 — done. Код закрыт до этого прогона: коммит 783bd55 добавил autouse-фикстуру в
`tests/conftest.py`, снимающую все `RECAP_*` (вариант 1). Проверено сейчас: `.venv/Scripts/pytest.exe -q`
→ 364 passed, красного теста нет. Ключ ротирован (подтверждено владельцем).

2026-08-08 — /burndown (проверка актуальности + волна 1) — done: SEC-006 (потоковый sha256 против
digests PyPI до распаковки), ARCH-006 (нормализация переводов строк в summary_schema, вариант 1;
чинит оба round-trip'а — Markdown и новый plain), REL-009 (PULL_IDLE_TIMEOUT на каждое чтение,
вариант 2 из issue физически невозможен: сокет после таймаута мёртв), ARCH-005 (cancel проброшен в
resummarize_one; гранулярность — вокруг вызова LLM, LLMSummarizer остался «тупым»), CONV-002
(known-first-party удалён), AGENT-009 (п.1 про запрет унификации устарел — снят коммитом 0ac5799;
сделаны карта +cuda_support/ollama_support, режим lecture, правило «доки — часть изменения»).
CODE-008 → wont-do: не дефект.

2026-08-08 — CODE-008 — wont-do. Посылка issue опровергнута: коммит da9d474 прямым текстом
мотивирует удаление duration-probe («info.duration was never zero for these inputs, confirmed in
recap-bridge.log»), реальной причиной молчащего прогресса был redirect_stdout=True у rich, и этот
фикс закрыт регрессионным тестом. В recap-bridge.log нет ни одного прогона с нулевой длительностью.
Ревью прочитало гипотезу из сообщения 3dd5381 как описание состояния.

2026-08-08 — ARCH-005 — НЕ проверено вручную: реальная кнопка «Остановить» в запущенном приложении
во время «Повторить суммаризацию» (нет GUI здесь). Rust не менялся, компилировать было нечего.

2026-08-08 — /burndown (волна 2) — done: SEC-008+PERF-003 (одна переписанная `_extract_dlls`: отказ
членам вида `nvidia/../../evil/bin/x.dll`, потоковое copyfileobj, опрос cancel между членами —
поэтому один коммит на две issue), CODE-010 (мок отдаёт cancelled и пишет его в историю; заодно
зеркально починена отмена в `resummarize` мока — та же поломка в том же файле, названа в коммите).

2026-08-08 — /burndown (волна 3) — done: SEC-007 (запись из webview скоуплена: save_summary только
по summary_path из истории, base_name — обязан быть простым именем файла), CODE-009 (схема реально
уходит в response_format, с деградацией на json_object и дальше на текстовый путь), DOC-005,
AGENT-010 (память переписана).

2026-08-08 — ARCH-007 — новая issue, заведена в этот прогон. Найдена субагентом при закрытии
ARCH-006 и перепроверена: `to_plain ↔ parse_plain` теряет структуру на CAPS-метке списка и на прозе,
заканчивающейся двоеточием. Тот же класс, что ARCH-006, но триггер бытовее (пользователь набрал
метку капсом в редакторе десктопа). Взята в работу сразу.

2026-08-08 — REL-010 — решение владельца: детекция NVIDIA GPU ДО скачивания CUDA-либ; при
device=cuda без карты — ошибка без загрузки, при device=auto — откат на CPU, но с явным сообщением
в логе и в UI (тихого CPU быть не должно).

2026-08-08 — CODE-009 — НЕ проверено: живой ответ OpenAI/xAI на `json_schema` без `strict: true`.
Если провайдер его отвергнет, каждый структурированный прогон будет платить один лишний round-trip
и деградировать на json_object. Проверка на стороне пользователя: прогнать саммари через OpenAI и
поискать в логе `Provider rejected response_format=json_schema`.

2026-08-08 — /burndown (волна 4, агентская и упаковочная) — done: AGENT-011 (runtime-знание
перенесено из памяти в AGENTS.md), AGENT-012 (чеклист переписан), AGENT-013 (docs/manual-qa-pending.md
как журнал долга ручной QA + правило рядом с honesty-правилом), AGENT-014 (по решению владельца —
вариант 2), DEP-005 (тест сверки с uv.lock), DEP-006 (pyinstaller запинен в группе packaging).
AGENT-015 → wont-do.

2026-08-08 — AGENT-014 — решение владельца: права остаются в settings.local.json (свежий клон не
должен наследовать чужой allowlist), комментарий в .gitignore перестал обещать общий settings.json.

2026-08-08 — DEP-006 — ТРЕБУЕТСЯ ДЕЙСТВИЕ ПОЛЬЗОВАТЕЛЯ: прогнать `uv lock` на Windows, чтобы
pyinstaller попал в uv.lock (uv из WSL запрещён).

2026-08-08 — /burndown (волна 5) — done: ARCH-007, REL-010, REL-011, REL-013, CODE-012, DOC-004.
Заодно поправлены три ложных утверждения README про `-f/--format` (обещал `telegram|json` для
`run`/`batch`, у которых флага нет) — найдено агентом DOC-004 и вынесено в отдельный коммит.

2026-08-08 — REL-010 — гипотеза issue про `auto` ОПРОВЕРГНУТА на живом железе: на машине с картой
`auto` выбирает CUDA (ctranslate2 смотрит только на драйвер) и падает на первом matmul с
`Library cublas64_12.dll is not found`, а не «тихо уходит на CPU». Тихий CPU бывает только на машине
БЕЗ карты — эту часть и закрыли. ОТКРЫТЫЙ ПРОДУКТОВЫЙ ВОПРОС: должен ли `auto` на машине с картой
предлагать загрузку 2 ГБ или принудительно уходить на CPU. Пока только задокументировано в
docs/portable-build.md.

2026-08-08 — REL-011 — сознательное отклонение от рекомендованного варианта 1 (PATH из Rust) в пользу
варианта 2 (поиск на стороне Python): покрывается тестами отсюда, не добавляет непроверяемой
Rust-логики и работает также при прямом запуске recap-bridge.exe.

2026-08-08 — DOC-003 — скоуп пересобран по факту, а не по тексту issue: `download`-шаг добавил агент
REL-010, `save_summary` — агент SEC-007, отмену resummarize — агент ARCH-005. Реально не хватало двух
команд (`check_model`, `pull_model`) и устаревшего примера `get_settings` (без `output_dir` и
`api_keys_configured`, с чужим `max_transcript_chars`).

2026-08-08 — вне бэклога, найдено агентом при закрытии SEC-009 и починено сразу: `_streaming`
разбирал `cancel_flag` ВНЕ error boundary. До дедупликации CODE-011 это стоило одного упавшего
вызова, после — падения долгоживущего воркера вместе с прогретой Whisper-моделью. Коммит 2df2950.

2026-08-08 — /burndown (финал волны 6) — done: SEC-009, CODE-011, REL-012, REL-014, DOC-003.
REL-014 был `hypothesis` — подтвердил механику сам на Windows-питоне венва: `os.rename` файла,
открытого другим (или тем же) процессом, даёт `PermissionError [WinError 32]`, а `logging` глотает
это в `handleError`, теряя запись. Решение — вариант 1: воркер пишет в `recap-bridge-serve.log`,
одиночные команды — в `recap-bridge.log`.

2026-08-08 — ИТОГ ПРОГОНА. Из 32 issue ревью 2026-07-05: 30 done, CODE-008 → wont-do (не дефект),
AGENT-015 → wont-do (рекомендованное действие — «наблюдать»). Плюс заведена и закрыта новая ARCH-007.
Финальная проверка на чистом дереве: pytest 442, ruff, mypy, npm lint/test/build, cargo check+clippy —
всё зелёное. Промежуточные прогоны шли на дереве с чужими незакоммиченными правками; авторитетен
финальный. Весь долг ручной проверки на Windows — в docs/manual-qa-pending.md.

2026-07-02 — финал. Все 40 issue закрыты. AGENT-003 (импорт подтверждён), AGENT-005 (allowlist через
/update-config + deny uv), DEP-003 (uv lock выполнен пользователем). Tailwind 4 ждёт визуального обзора
в запущенном app (сборка/тесты зелёные), но реализация закрыта.
