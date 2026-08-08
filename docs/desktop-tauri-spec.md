# ТЗ: desktop-версия Recap на Tauri

## 1. Цель

Сделать красивую и легкую desktop-версию Recap для Windows. Приложение должно закрывать основной сценарий:

> пользователь выбирает один аудиофайл встречи, запускает полный pipeline, получает transcript и summary, при необходимости правит summary и экспортирует результат.

Desktop-приложение не должно переписывать бизнес-логику транскрибации и суммаризации. Оно должно использовать существующую Python-логику проекта и расширить ее только там, где это нужно для удобного GUI.

## 2. Зафиксированные продуктовые решения

- Язык интерфейса MVP: русский.
- Платформа MVP: Windows first.
- Основной сценарий MVP: один аудиофайл -> full run -> transcript + summary.
- Не включать batch в первый релиз.
- Интеграция Tauri и Python: через bridge к Python workflow, а не через прямой shell-вызов CLI как основную архитектуру.
- История запусков: локальный JSON.
- API keys: хранить через Windows Credential Manager / OS keychain.
- Summary можно редактировать перед копированием/экспортом.
- Transcript в MVP readonly.
- Прогресс: live-лог этапов, summary показывается финально после завершения LLM-запроса.
- Экспорт: Markdown `.md`, обычный текст `.txt`, HTML `.html`, JSON.
- Settings: полноценный экран настроек.
- Preprocessing: в desktop всегда включён (toggle `enabled` в настройках убран); показываем только базовые параметры.
- History хранит метаданные и ссылки на файлы результата, не копии transcript/summary.

## 3. MVP scope

### Включить

- Выбор одного аудиофайла через file picker.
- Drag-and-drop аудиофайла в центральную область.
- Запуск полного pipeline:
  - preprocessing, если включен;
  - transcription;
  - сохранение transcript;
  - summarization;
  - сохранение summary.
- Отображение этапов:
  - `Подготовка`;
  - `Транскрибация`;
  - `Суммаризация`;
  - `Экспорт`.
- Live-лог выполнения.
- Просмотр transcript.
- Просмотр и редактирование summary.
- Копирование summary.
- Экспорт summary в Markdown/plain/HTML/JSON.
- Открытие папки с результатами.
- История последних запусков.
- Экран настроек:
  - transcription;
  - summarization;
  - preprocessing;
  - paths;
  - privacy acknowledgement.
- Хранение/обновление API key через keychain.
- Нормальные состояния ошибок.

### Не включать в MVP

- Batch queue.
- Мультифайловый импорт.
- Редактирование transcript.
- Streaming токенов summary в UI.
- Встроенный аудиоплеер.
- Авторизация пользователей.
- Cloud sync.
- Автоматическое обновление приложения.
- macOS/Linux packaging.

## 4. Архитектурные требования

Текущий CLI остается рабочим. Для desktop нужно вынести workflow из `src/cli.py` в reusable Python-модуль.

Рекомендуемая структура Python-части:

```text
src/
├── cli.py
├── workflows.py        # reusable сценарии для CLI и desktop bridge
├── desktop_bridge.py   # JSON/IPC-friendly facade для Tauri
└── ...
```

`cli.py` должен остаться тонкой командной оболочкой:

- парсит аргументы;
- вызывает функции из `workflows.py`;
- переводит исключения в user-facing CLI ошибки;
- продолжает использовать `utils.write_text_atomic()`.

`workflows.py` должен владеть повторно используемыми сценариями:

- `run_one_file(...)` — единственный оркестратор пайплайна (preprocess → transcribe → write →
  summarize → export); `resummarize_one(...)` для повторной суммаризации по готовому транскрипту;
- события прогресса через callback;
- возврат структурированного результата (`RunResult`).

### CLI ↔ desktop: намеренное расхождение (ARCH-001)

`run_one_file` — общий движок, но CLI и desktop сознательно отличаются, и это **намеренно**:

- **Язык сообщений.** `RunResult.error_message` из `workflows` — на русском (для UI). CLI-команды
  (`summarize`/`run`/`batch`) печатают собственные **английские** сообщения и коды выхода.
- **Файлы результата.** CLI пишет один файл под выбранный `--format` (markdown `.txt` **или** json
  `.json`). Desktop (`run_one_file` с `summary_format="plain"`) всегда пишет `.txt` **и** `.json`
  рядом; экспорт из UI даёт markdown `.md`, plain `.txt`, HTML `.html`, JSON `.json`.
- **Формат редактируемого текста.** Вкладка «Саммари» показывает и правит простой текст для
  Telegram (`formatters.to_plain`), и именно он лежит в `.txt` разбора и в `RunResult.summary_text`.
  CLI остаётся на Markdown. Сохранение/экспорт разбирают текст через `parse_summary_text`, который
  сам определяет форму, поэтому записи истории, созданные до перехода, продолжают открываться.
- **Пустая транскрипция.** `run`/`run_one_file` трактуют «речь не распознана» как ошибку (exit 1 /
  статус `failed`); `batch` считает такой файл обработанным и идёт дальше. Это расхождение
  зафиксировано как открытый вопрос (см. roadmap ARCH-001) — унификация изменит поведение `batch`.

Пока это расхождение задокументировано, полная унификация CLI через `run_one_file` (вариант 1
ARCH-001) отложена: она потребует i18n сообщений и смены семантики выходных файлов CLI — это решение
за владельцем проекта. Общий «хвост» summarize→format→write внутри `cli.py` уже вынесен в хелперы.

`desktop_bridge.py` должен давать Tauri простой JSON-friendly API:

- загрузить текущие настройки;
- сохранить настройки;
- получить/сохранить API key через keychain;
- запустить one-file run;
- отменить текущий run, если это реализуемо в выбранной модели процесса;
- получить историю;
- удалить запись истории;
- экспортировать summary.

## 5. Важные правила существующего проекта

Агент должен соблюдать текущие правила Recap:

- Строгая nested-конфигурация в `src/config.py`; неизвестные ключи запрещены.
- `Settings` и вложенные sections frozen dataclasses.
- Resolution order: CLI flags > env vars > `config.yaml` > defaults.
- Env vars имеют формат `RECAP_...`; нет fallback на `OPENAI_API_KEY`.
- Provider wiring только через `providers.factory`.
- Lazy imports для тяжелых provider-зависимостей сохранять.
- `src/cli.py` остается единственной CLI error boundary.
- Все файловые записи идут через `utils.write_text_atomic()`.
- Transcript сохраняется до LLM-вызова.
- При падении LLM transcript должен остаться сохраненным.
- `LLMSummarizer.summarize()` сейчас streams tokens в stderr и возвращает полный string.
- `Transcript.segments` immutable tuple.
- `preprocess` command всегда запускает ffmpeg, но `run` использует `prepared_audio()`, который уважает `preprocessing.enabled`.

## 6. Frontend stack

Рекомендуемый стек:

```text
Tauri 2
React
TypeScript
Vite
Tailwind CSS
shadcn/ui
lucide-react
```

UI должен быть desktop-first: плотный, рабочий, аккуратный. Не делать landing page.

## 7. Основные экраны

### Главный экран

Три области:

- левая sidebar: бренд, новый запуск, история, настройки;
- центральная рабочая область: выбранный файл, прогресс, tabs результата;
- правая inspector-панель: настройки текущего запуска.

Основные элементы:

- `Новый разбор`;
- зона выбора/drag-and-drop файла;
- имя файла, длительность/размер, если доступны;
- кнопка `Запустить`;
- progress steps;
- live-log;
- tabs: `Транскрипт`, `Резюме`, `Лог`.

### Result view

- Transcript readonly с таймкодами.
- Summary editable textarea/editor.
- Кнопки:
  - `Копировать`;
  - `Экспорт`;
  - `Открыть папку`;
  - `Повторить`.
- Состояние partial success:
  - transcript сохранен;
  - summary не создан из-за ошибки LLM;
  - UI предлагает повторить только суммаризацию после исправления настроек.

### Settings

Секции:

- `Транскрибация`;
- `Суммаризация`;
- `Предобработка`;
- `Пути`;
- `Приватность`;
- `Ключи API`.

Не показывать пользователю raw stack traces. Ошибки должны быть понятными и короткими, с техническими деталями в логах.

## 8. Settings MVP

### Транскрибация

Поля:

- language;
- model.provider: только `faster-whisper`;
- model.name;
- model.device: `cuda`, `cpu`, `auto`;
- model.compute_type: `default`, `float16`, `int8`, `int8_float16`, `float32`;
- beam_size;
- vad_filter;
- condition_on_previous_text.

### Суммаризация

Поля:

- language;
- mode: `brief`, `medium`, `detailed`;
- max_transcript_chars;
- timeout_seconds;
- retries;
- chunking_mode: `chunk`, `truncate`;
- model.provider: `openai`, `xai`, `ollama`, `lm-studio`, `vllm`;
- model.name;
- model.base_url;
- model.num_ctx.

API key показывать отдельно:

- masked;
- `Сохранить ключ`;
- `Удалить ключ`;
- `Проверить подключение`.

### Предобработка

Поля:

- enabled;
- sample_rate;
- channels;
- loudness_normalization;
- target_lufs;
- true_peak_db;
- loudness_range;
- highpass_hz;
- keep_temp.

Для MVP можно скрыть `codec`, оставив значение `pcm_s16le`.

### Пути

Поля:

- default audio path;
- transcript output path;
- summary output path;
- app data/history path readonly или advanced.

### Приватность

- `privacy_ack`;
- понятное предупреждение, что при внешнем provider transcript отправляется во внешний endpoint.

## 9. История

Хранить локальный JSON в app data директории Tauri.

Запись истории:

```json
{
  "id": "uuid",
  "created_at": "2026-06-19T12:00:00+03:00",
  "audio_path": "C:/path/to/meeting.mp3",
  "audio_name": "meeting.mp3",
  "status": "success",
  "transcript_path": "C:/path/to/transcript.txt",
  "summary_path": "C:/path/to/summary.txt",
  "summary_json_path": "C:/path/to/summary.json",
  "provider": "ollama",
  "model": "qwen3.5:latest",
  "mode": "medium",
  "transcription_language": "ru",
  "summary_language": "ru",
  "duration_seconds": null,
  "error_message": null
}
```

Статусы:

- `running`;
- `success`;
- `partial_success`;
- `failed`;
- `cancelled`.

История хранит ссылки на файлы. Не дублировать полный transcript/summary внутри history JSON.

## 10. Error states

Обязательные состояния:

- audio file не найден;
- unsupported audio extension;
- config validation failed;
- missing ffmpeg при включенном preprocessing;
- faster-whisper/CUDA/model load error;
- empty transcription/no speech detected;
- external provider privacy warning;
- missing API key для внешнего provider;
- LLM timeout;
- LLM provider error;
- output path недоступен;
- keychain read/write error.

Partial success:

- если transcription успешно завершилась и transcript записан, но LLM упал, UI показывает transcript и статус `partial_success`;
- пользователь может исправить настройки и повторить summarization.

## 11. Acceptance criteria

- Пользователь может выбрать один аудиофайл и запустить pipeline.
- Transcript записывается на диск до начала LLM-суммаризации.
- При LLM-ошибке transcript остается доступным в UI и на диске.
- Summary можно редактировать после генерации.
- Экспорт работает в Markdown `.md`, plain `.txt`, HTML `.html`, JSON.
- История показывает последние запуски и открывает связанные файлы/папки.
- Настройки читаются из текущей nested config schema и сохраняются без unknown keys.
- API key не пишется открытым текстом в `config.yaml`.
- UI не блокируется во время долгой транскрибации.
- Ошибки показаны понятным русским текстом.
- CLI остается рабочим и покрытым текущими тестами.

## 12. Проверки

Перед сдачей агент должен выполнить:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check src/
.venv\Scripts\mypy.exe src/
```

Если добавляется frontend:

```powershell
npm run lint
npm run test
npm run build
```

И вручную проверить Tauri dev build на Windows:

- запуск приложения;
- выбор файла;
- запуск pipeline на коротком аудио или mock-mode;
- partial success при искусственной LLM-ошибке;
- сохранение настроек;
- сохранение/удаление API key;
- экспорт файлов.
