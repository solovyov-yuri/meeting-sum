# Tauri <-> Python bridge contract

## 1. Цель bridge

Bridge дает Tauri frontend доступ к существующей Python-логике Recap без shell-first архитектуры. CLI остается поддерживаемым, но desktop не должен парсить human-oriented stdout/stderr как основной контракт.

Bridge должен быть JSON-friendly и устойчивым к долгим задачам.

## 2. Рекомендуемые Python-модели

```python
@dataclass(frozen=True)
class RunOptions:
    audio_path: Path | None = None
    transcript_path: Path | None = None
    summary_path: Path | None = None
    transcription_language: str | None = None
    summary_language: str | None = None
    provider: str | None = None
    model: str | None = None
    mode: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    step: str
    status: str
    message: str
    percent: float | None = None
    path: Path | None = None


@dataclass(frozen=True)
class RunResult:
    status: str
    transcript_path: Path | None
    summary_path: Path | None
    summary_json_path: Path | None
    transcript_text: str | None
    summary_text: str | None
    error_message: str | None = None
    output_path: Path | None = None  # preprocess-only: the produced *.preprocessed.wav
```

Допустимые `step`:

- `download` — разовая загрузка библиотек GPU (CUDA) в portable-сборке перед распознаванием;
  в обычной сборке не появляется. Здесь же приходит `error`, если выбран `device: cuda`, а
  видеокарты NVIDIA в машине нет (загрузка при этом не начинается);
- `preprocess`;
- `transcribe` — при `device: auto` без видеокарты NVIDIA сюда приходит `warning` о том, что
  распознавание пойдёт на CPU и будет медленнее (сам запуск продолжается);
- `summarize`;
- `export`.

Допустимые `status` для event:

- `pending`;
- `running`;
- `success`;
- `warning`;
- `error`;
- `cancelled`.

Допустимые `RunResult.status`:

- `success`;
- `partial_success`;
- `failed`;
- `cancelled`.

## 3. Python workflow API

Минимальный API:

```python
def run_one_file(
    options: RunOptions,
    *,
    progress: Callable[[ProgressEvent], None] | None = None,
) -> RunResult:
    ...
```

Требования:

- загружать `Settings.load()`;
- применять overrides из `RunOptions`;
- использовать `providers.factory.make_transcriber()` и `make_summarizer()`;
- использовать `prepared_audio()`;
- записывать transcript до LLM;
- возвращать `partial_success`, если transcript записан, но summarization failed;
- все файловые записи делать через `write_text_atomic()`;
- не ловить исключения слишком широко внутри низкоуровневых provider-функций.

## 4. Desktop bridge commands

Tauri commands могут быть реализованы напрямую в Rust с вызовом Python-процесса/bridge, либо через выбранный IPC-механизм. Для frontend контракт должен выглядеть так:

### `get_settings`

Input:

```json
{}
```

Output:

```json
{
  "audio": "data/meeting.wav",
  "transcript": "data/transcript.txt",
  "summary": "data/summary.txt",
  "output_dir": null,
  "privacy_ack": false,
  "transcription": {
    "language": "ru",
    "model": {
      "provider": "faster-whisper",
      "name": "large-v3",
      "device": "cuda",
      "compute_type": "default",
      "beam_size": 5,
      "vad_filter": true,
      "condition_on_previous_text": true
    }
  },
  "summarization": {
    "language": null,
    "mode": "medium",
    "max_transcript_chars": 42000,
    "timeout_seconds": 60.0,
    "retries": 2,
    "chunking_mode": "chunk",
    "model": {
      "provider": "ollama",
      "name": "qwen3.5:latest",
      "api_key_configured": false,
      "base_url": null,
      "num_ctx": null
    }
  },
  "preprocessing": {
    "enabled": false,
    "sample_rate": 16000,
    "channels": 1,
    "codec": "pcm_s16le",
    "loudness_normalization": false,
    "target_lufs": -16.0,
    "true_peak_db": -1.5,
    "loudness_range": 11.0,
    "highpass_hz": null,
    "keep_temp": false
  },
  "api_keys_configured": {
    "openai": true,
    "xai": false,
    "ollama": false,
    "lm-studio": false,
    "vllm": false
  }
}
```

Важно: `api_key` не возвращать открытым текстом. `api_keys_configured` — маска наличия ключа по
каждому провайдеру (не только по сохранённому), чтобы UI показывал статус при переключении
провайдера в черновике настроек.

### `save_settings`

Input: nested config object без `api_key`.

Output:

```json
{ "ok": true }
```

Требования:

- сохранять только известные schema keys;
- перед записью прогонять validation через `Settings.load()` или эквивалентную проверку;
- не писать secrets в `config.yaml`.

### `set_api_key`

Input:

```json
{
  "provider": "openai",
  "api_key": "..."
}
```

Output:

```json
{ "ok": true }
```

Требования:

- хранить ключ через Windows Credential Manager / keychain;
- не логировать ключ;
- не возвращать ключ frontend после сохранения.

### `delete_api_key`

Input:

```json
{ "provider": "openai" }
```

Output:

```json
{ "ok": true }
```

### `run_recap`

Input:

```json
{
  "run_mode": "full",
  "audio_path": "C:/meetings/meeting.mp3",
  "transcript_path": null,
  "summary_path": null,
  "overrides": {
    "transcription_language": "ru",
    "summary_language": "ru",
    "provider": "ollama",
    "model": "qwen3.5:latest",
    "mode": "medium"
  }
}
```

`run_mode` selects the pipeline slice (default `"full"`) — **distinct from `overrides.mode`**, which is
the *summary* mode (brief/medium/detailed/lecture — `SUMMARY_MODES` в `prompts.py`):

- `"full"` — preprocess (forced on) → transcribe → summarize → export.
- `"transcribe"` — preprocess → transcribe only; returns `success` with the transcript written and no
  summary (empty transcript is success-with-warning). No summarization key required.
- `"preprocess"` — ffmpeg only; writes `<output_dir|audio-dir>/<stem>.preprocessed.wav`, returned on
  `output_path` and the success event's `path`. `audio_path` is required for these three.
- Standalone `"summarize"` is the separate `resummarize` command (input is a transcript, not audio).

Progress events:

```json
{
  "step": "transcribe",
  "status": "running",
  "message": "Транскрибация началась",
  "percent": null,
  "path": null
}
```

Final output:

```json
{
  "status": "success",
  "transcript_path": "C:/.../transcript.txt",
  "summary_path": "C:/.../summary.txt",
  "summary_json_path": "C:/.../summary.json",
  "transcript_text": "...",
  "summary_text": "...",
  "error_message": null,
  "output_path": null
}
```

`output_path` is set only by `run_mode: "preprocess"` (the produced `*.preprocessed.wav`); otherwise null.

### `serve` — persistent warm-model worker (PERF-001)

To avoid reloading the Whisper model (~10–60 s for large-v3) on every run, the Rust host does **not**
spawn a fresh process per `run_recap`. Instead it keeps one `recap-bridge serve` process alive and
routes runs through it:

- `serve` reads **one JSON run-request per line** on stdin and, per run, streams the same framing as
  `run_recap` (`{"type":"progress"}` events then a terminal `{"type":"result"}` / `{"type":"error"}`
  line). Its stdout stays open between runs — the host reads until the terminal line, not EOF.
- The worker caches exactly one transcriber, keyed on the transcription model fields; changing the
  model drops the old one (freeing GPU memory) before building the new.
- Runs are serialised by the host (a mutex), so `serve` only ever handles one request at a time.
- **Fallback:** if the worker fails to spawn or its pipe breaks, the host falls back to a fresh
  spawn-per-call `run_recap` — slow (model reloads) but correct.
- Only `run_recap` uses the worker. `resummarize` is LLM-only (no model) and stays spawn-per-call.

### `resummarize`

**Streaming** (second NDJSON channel besides `run_recap`). Re-runs only summarization on an existing
transcript — the partial_success recovery path («Повторить суммаризацию»); never re-transcribes.

Input: same shape as `run_recap`, but `transcript_path` must point at an existing transcript on disk
(`audio_path` is carried for history metadata only, not read). Progress events and the final output
object are identical to `run_recap`, cancellation included (`cancel_flag`, see §6).

### `export_summary`

Input:

```json
{
  "summary_json_path": "C:/.../meeting_2026_06_19_summary.json",
  "summary_text": "...edited plain text; Markdown from pre-plain entries (fallback if the base json is missing/empty/corrupt)...",
  "formats": ["markdown", "plain", "html", "json"],
  "target_dir": "C:/meetings/output",
  "base_name": "meeting_2026_06_19",
  "mode": "medium"
}
```

Output:

```json
{
  "markdown_path": "C:/.../meeting_2026_06_19_summary.md",
  "plain_path": "C:/.../meeting_2026_06_19_summary_plain.txt",
  "html_path": "C:/.../meeting_2026_06_19_summary.html",
  "json_path": "C:/.../meeting_2026_06_19_summary.json"
}
```

Источник данных для всех форматов — базовый `.json` (`summary_json_path`). Фолбэк на разбор
`summary_text` срабатывает, если файла нет, если это старый `{mode, summary}` без `blocks`, а также
если файл повреждён (обрезан, отредактирован руками, не UTF-8) — повреждённый `.json` больше не
роняет экспорт целиком, а лишь пишется предупреждение в лог bridge. Если и текст пуст, экспорт
завершается ошибкой `Нечего экспортировать: …` **до** записи файлов — пустые файлы не создаются.

Ограничения на путь записи (все файлы кладутся строго в `target_dir`):

- `target_dir` должен уже существовать — каталоги не создаются.
- `base_name` — одиночный компонент имени файла: пустая строка, `.`, `..`, разделители пути
  (`/`, `\`), `:` (диск и ADS в Windows) и управляющие символы отклоняются с ошибкой
  `Недопустимое имя файла для экспорта`. Пробелы, пунктуация и не-ASCII допустимы (это обычно
  stem аудиофайла).

### `save_summary`

Перезаписывает отредактированное саммари (`.txt`) и пересобирает соседний `.json` из его текста.

Input:

```json
{
  "summary_text": "...edited plain text (Markdown from pre-plain entries also parses)...",
  "summary_path": "C:/.../meeting_2026_06_19_summary.txt",
  "mode": "medium"
}
```

Output:

```json
{
  "summary_path": "C:/.../meeting_2026_06_19_summary.txt",
  "json_path": "C:/.../meeting_2026_06_19_summary.json"
}
```

`summary_path` должен совпадать с `summary_path` существующей записи истории (сравнение по
нормализованному пути) — иначе ошибка `Файл саммари не найден в истории запусков`. Это ровно тот
путь, который фронтенд получает из результата запуска или из открытой записи истории; записать
куда-либо ещё команда не позволяет. Каталог данных приложения тоже недоступен для записи: в нём
лежат `config.yaml` и `history.json`.

### `check_model`

Проверка, что настроенная модель суммаризации доступна. Нужна только Ollama: у остальных провайдеров
нечего «доустанавливать», поэтому ответ всегда `installed: true`. Недоступная Ollama тоже даёт
`installed: true` — запуск не блокируется, реальную ошибку покажет сам прогон.

Input:

```json
{}
```

Output:

```json
{
  "installed": false,
  "provider": "ollama",
  "model": "qwen3.5:latest",
  "base_url": "http://localhost:11434/v1"
}
```

### `pull_model` (стриминг)

Загрузка модели в Ollama по ответу `check_model` с `installed: false`. Стримит те же
`{"type":"progress"}`-строки, что `run_recap`, шагом `download`, и завершается обычным `result`
с `RunResult`-формой (пути пустые). Отменяется тем же `cancel_flag` (§6); Ollama при этом продолжает
качать на своей стороне, поэтому отменённая загрузка может всё же завершиться и попасть в кэш.

Input:

```json
{
  "cancel_flag": "C:/.../recap-cancel-<uuid>.flag"
}
```

Адрес и имя модели **не берутся из payload** — мост резолвит их из сохранённых настроек, как
`check_model`, и отказывает, если провайдер не `ollama`. UI и так лишь возвращает то, что ему отдал
`check_model`, поэтому лишние поля в payload просто игнорируются.

Молчащий сокет не подвешивает загрузку навсегда: таймаут ограничивает ожидание каждого чтения
(`ollama_support.PULL_IDLE_TIMEOUT`), но не общую длительность — многогигабайтная модель качается
столько, сколько идут байты.

### `get_history`

Output:

```json
{
  "items": []
}
```

### `delete_history_item`

Input:

```json
{ "id": "uuid" }
```

Output:

```json
{ "ok": true }
```

Удаляет только запись истории, не файлы.

### `test_connection`

Проверяет доступность LLM-провайдера с сохранёнными настройками/ключом.

Input:

```json
{ "provider": "openai" }
```

Output:

```json
{ "ok": true, "message": "Подключение успешно." }
```

### `list_models`

Запрашивает список моделей у провайдера через OpenAI-совместимый `GET /v1/models` (реальный
сетевой вызов с коротким таймаутом). Никогда не бросает — при любой ошибке (офлайн, нет ключа,
сервер недоступен) возвращает пустой список и текст ошибки, а UI откатывается к ручному вводу.
Base URL разрешается по логике CODE-005 (доверяем сохранённому base_url только для того же
провайдера, иначе — пресет).

Input:

```json
{ "provider": "openai" }
```

Output:

```json
{ "models": ["gpt-4o", "gpt-4o-mini"], "error": null }
```

### `read_text`

Читает файл результата с диска (используется, чтобы заново открыть запись истории). Отсутствующий
файл — не ошибка.

Input:

```json
{ "path": "C:/.../summary.txt" }
```

Output:

```json
{ "text": "...", "exists": true }
```

Отсутствующий файл: `{ "text": null, "exists": false }`; ошибка чтения добавляет `"error"`.

## 5. Secrets

Для Python можно рассмотреть пакет `keyring`. Для Tauri/Rust можно рассмотреть plugin/store или Rust crate, который работает с Windows Credential Manager.

Требования независимо от реализации:

- secrets не должны попадать в `config.yaml`;
- secrets не должны попадать в history JSON;
- secrets не должны попадать в логи;
- UI показывает только masked state: `ключ сохранен` / `ключ не сохранен`.

## 6. Отмена выполнения

Для MVP cancel можно сделать best-effort:

- frontend показывает `Остановить`;
- bridge выставляет cancellation flag;
- workflow проверяет flag между этапами.

Полное прерывание faster-whisper внутри текущего вызова не обязательно для MVP, если это явно описано в UI:

```text
Остановка произойдет после завершения текущего этапа.
```

### Реализация (ARCH-002)

Отмена кооперативная, через flag-файл — процесс bridge **не** убивается:

- на каждый `run_recap`/`resummarize` Rust генерирует уникальный путь и передаёт его в payload
  как `cancel_flag` (ключ съедается мостом в `_streaming`, до сборки `RunOptions`);
- по нажатию `Остановить` (`cancel_run`) watcher-поток в Rust создаёт этот файл;
- `_streaming` строит `cancel = Path(cancel_flag).exists` и передаёт его и в `run_one_file`, и в
  `resummarize_one`; оба проверяют флаг между этапами и возвращают `RunResult("cancelled", …)` — с
  сохранённым `transcript_path`, если транскрипт уже записан (для resummarize он всегда на диске);
- Rust дочитывает stdout до реального `result` (не синтезирует `cancelled` сам), поэтому отменённый
  запуск попадает в историю со статусом `cancelled` и указателем на транскрипт;
- так как процесс не убит, `finally` в Python отрабатывает — временный WAV удаляется, ffmpeg не
  висит. Rust удаляет flag-файл по завершении запуска.

Ограничение: во время самой транскрибации отмена срабатывает на границе этапа.
При суммаризации флаг проверяется перед запросами и при чтении потока; у Ollama также между
фрагментами и уровнями объединения. При отмене HTTP-поток закрывается, возвращается `cancelled`,
саммари не сохраняется, транскрипт остаётся. Ожидание данных из молчащего сокета ограничено
настроенным `timeout_seconds`; это не мгновенная отмена во время заблокированного чтения.
Фолбэк JSON → текст не перехватывает отмену. Проверка после генерации сохранена.

Ollama использует `/api/chat` с `think: false`, `options.num_ctx` (null в настройках → 8192),
лимитом ответа и запретом автоматического обрезания/сдвига контекста. `max_transcript_chars`
остаётся верхним ограничением; фактический фрагмент дополнительно ограничивается оценкой токенов
с резервом под инструкции/схему/ответ. Прогресс фрагментов идёт обычными событиями `summarize/running`
без изменения NDJSON-схемы. Промежуточные результаты кешируются только в памяти текущего summarizer
для повтора финального оформления. Промежуточный этап Ollama возвращает JSON с номерами отрывков;
проверяется диапазон, число и уникальность номеров, а в следующий этап поступают только дословные
отрывки исходного текста. Пересказ выполняется один раз при финальном оформлении.
Ошибка незавершённого ответа или несходящегося объединения
проходит через прежнюю границу `partial_success`; молчаливого обрезания в Ollama `chunk` нет.
В полном `run_recap` перед локальной Ollama веса Whisper выгружаются, даже если объект
распознавателя кешируется воркером. На следующей транскрибации они загружаются обратно.
Режим только транскрибации сохраняет тёплый кеш; отдельный процесс `resummarize` не управляет
кешем Whisper в другом процессе.

## 7. Logging

Файлы лога в `<data dir>/logs/`: `recap-bridge-serve.log` — долгоживущий воркер (там прогоны:
транскрибация, суммаризация, CUDA), `recap-bridge.log` — spawn-per-call команды (настройки, экспорт,
история). Файлы разные намеренно: процессы работают одновременно, а ротация переименовывает файл, что
на Windows невозможно, пока его держит открытым другой процесс — `logging` глотает такую ошибку и
теряет запись. Оба файла ротируются по 1 МБ, 3 бэкапа.

Bridge должен различать:

- user-facing event message;
- technical details for logs.

Frontend показывает короткие сообщения. Детальные exception strings можно хранить в log tab, но не показывать как главный error copy.
