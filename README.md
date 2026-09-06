# recap

Инструмент для транскрибации аудиозаписей встреч и автоматического составления саммари в формате Telegram.

**Пайплайн:** WAV → [Whisper large-v3] → транскрипция → [LLM] → саммари в Telegram Markdown.

## Требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- NVIDIA GPU с CUDA (для Whisper)
- Локальный LLM-сервер или API-ключ OpenAI

## Установка

```bash
git clone https://github.com/solovyov-yuri/recap.git
cd recap
uv sync
```

NVIDIA CUDA-библиотеки (cublas, cudnn) устанавливаются как Python-пакеты внутри venv — дополнительной системной установки не нужно. Они помечены `sys_platform != 'darwin'`, поэтому на **macOS** (где этих wheels нет) `uv sync` не падает; транскрибация там идёт на CPU (`transcription.model.device: cpu`).

## Конфигурация

Приоритет: **CLI-флаги > переменные среды > `config.yaml` > умолчания**.

```bash
cp config.yaml.example config.yaml
```

### config.yaml

Конфигурация — **вложенная**: две секции `transcription` и `summarization`, в каждой подсекция `model`.

```yaml
transcription:
  language: ru                 # язык для Whisper
  model:
    provider: faster-whisper   # поддерживается только faster-whisper
    name: large-v3
summarization:
  # language: ru               # язык промптов LLM; по умолчанию ru
  mode: medium                 # brief | medium | detailed | lecture
  max_transcript_chars: 42000  # лимит одного LLM-запроса; длинные транскрипты разбиваются на чанки (chunking_mode: chunk)
  model:
    provider: ollama           # openai | xai | ollama | lm-studio | vllm
    name: qwen3.5:latest
    # api_key: sk-...
    # base_url: http://...
```

`config.yaml` не коммитится (в `.gitignore`). Полный список полей — в `config.yaml.example`.

> **Без обратной совместимости:** старые плоские ключи (`provider`, `model`, `whisper_model`, `summary_mode`, …) больше не поддерживаются — загрузка падает с ошибкой о неизвестном ключе.

### Настройки Whisper

Все поля — внутри `transcription.model`:

| Поле | Умолчание | Описание |
|---|---|---|
| `transcription.model.device` | `cuda` | `cuda` / `cpu` / `auto` |
| `transcription.model.compute_type` | `default` | `default` / `float16` / `int8` / `int8_float16` / `float32` |
| `transcription.model.beam_size` | `5` | Размер луча — точность vs скорость |
| `transcription.model.vad_filter` | `true` | Пропускать тихие участки |
| `transcription.model.condition_on_previous_text` | `true` | Улучшает связность, отключить для коротких клипов |

`compute_type: default` автоматически выбирает `float16` для CUDA и `int8` для CPU/auto.

**CPU (без GPU):**
```yaml
transcription:
  model:
    device: cpu
    # compute_type подбирается автоматически (int8)
```

**Явные настройки GPU:**
```yaml
transcription:
  model:
    device: cuda
    compute_type: float16   # быстро и точно
    beam_size: 1            # ещё быстрее, чуть менее точно
```

### Переменные среды

Переопределяют любое поле из `config.yaml`. Имена повторяют вложенный путь:

```bash
RECAP_SUMMARIZATION_MODEL_PROVIDER=openai
RECAP_SUMMARIZATION_MODEL_NAME=gpt-4o-mini
RECAP_SUMMARIZATION_MODEL_API_KEY=sk-...
RECAP_SUMMARIZATION_MAX_TRANSCRIPT_CHARS=30000
RECAP_TRANSCRIPTION_LANGUAGE=en
RECAP_TRANSCRIPTION_MODEL_DEVICE=cpu
```

### Провайдеры

| Провайдер | base_url (по умолчанию) |
|---|---|
| `openai` | api.openai.com |
| `xai` | https://api.x.ai/v1 |
| `ollama` | http://localhost:11434/v1 |
| `lm-studio` | http://localhost:1234/v1 |
| `vllm` | http://localhost:8000/v1 |

`base_url` можно переопределить вручную для нестандартных адресов.

**OpenAI:**
```yaml
summarization:
  model:
    provider: openai
    name: gpt-4o-mini
    api_key: sk-...
```

**Ollama:**
```yaml
summarization:
  model:
    provider: ollama
    name: qwen3.5:latest
```

Для Ollama Recap использует родной `/api/chat`: `model.num_ctx` действительно задаёт
контекст (по умолчанию 8192 токена; 4096 — профиль с меньшим расходом памяти).
Адрес по-прежнему можно указывать с окончанием `/v1`. Thinking отключён.
Длинные транскрипты обрабатываются последовательно: модель выбирает номера важных
отрывков, код проверяет номера и сохраняет дословные исходные отрывки. Если они ещё
не помещаются, отбор повторяется; свободный пересказ выполняется только при финальном
оформлении. Это предотвращает накопление выдумок при пересказе пересказов, но не гарантирует
полноты отбора или безошибочности итогового текста. Бюджет учитывает инструкции, JSON-схему и ответ;
`max_transcript_chars` остаётся дополнительным верхним пределом. Число токенов оценивается
с запасом по UTF-8, без скачивания токенизатора; Ollama получает запрет автоматического
обрезания контекста. Очень старые версии сервера могут не поддерживать этот запрет.
Если записи не удалось сократить или ответ оборвался, Recap сообщает ошибку, а не
сохраняет обрезанное саммари. Режим `truncate` по-прежнему намеренно отбрасывает хвост.
В десктопе виден текущий фрагмент; отмена проверяется между фрагментами и при чтении потока.
В полном запуске перед локальной Ollama выгружаются веса Whisper, чтобы две модели не
занимали память одновременно. Следующая транскрибация повторно загрузит веса.

Воспроизводимый локальный прогон своих транскриптов: `python scripts/benchmark_summaries.py --context 4096`.
По умолчанию читается `data/transcripts`, результаты и
замеры времени/памяти модели остаются в игнорируемом Git каталоге `data/summary-benchmark`.
Успешная генерация не заменяет проверки фактов: особенно проверяйте решения, имена и сроки
при плохом качестве распознавания исходной речи.

**xAI:**
```yaml
summarization:
  model:
    provider: xai
    name: grok-4
    api_key: xai-...
```

**LM Studio:**
```yaml
summarization:
  model:
    provider: lm-studio
    name: local-model
```

**vLLM:**
```yaml
summarization:
  model:
    provider: vllm
    name: Qwen/Qwen3-8B
```

**Кастомный endpoint:**
```yaml
summarization:
  model:
    provider: openai
    name: my-model
    base_url: http://my-server:9000/v1
    api_key: secret
```

## Использование

### Режимы саммари

| Режим | Описание |
|---|---|
| `brief` | 2–3 предложения, только суть, без структуры |
| `medium` | Тема + ключевые обсуждения + решения и задачи (по умолчанию) |
| `detailed` | Полный протокол: участники, ход обсуждения, задачи с ответственными и сроками |
| `lecture` | Конспект лекции или доклада: разделы с тезисами, определениями и примерами + блок «Главное» |

### Полный пайплайн

```bash
uv run recap run                               # data/meeting.wav, режим medium
uv run recap run path/to/call.wav -m brief     # краткое саммари
uv run recap run audio.wav -m detailed -p openai
```

Записывает транскрипцию в `data/transcript.txt`, саммари — в `data/summary.txt`.

### Пакетная обработка

```bash
uv run recap batch recordings/                    # все аудиофайлы в папке, вывод туда же
uv run recap batch recordings/ -o out/ -m brief   # в отдельную папку, краткое саммари
uv run recap batch recordings/ -p openai --model gpt-4o
```

Поддерживаемые расширения: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.mp4`, `.mkv`, `.webm`
(у видеофайлов берётся звуковая дорожка). Тот же список действует для `run` и десктоп-приложения.

Для каждого файла `{name}.{ext}` создаются:
- `{name}.txt` — транскрипция
- `{name}_summary.txt` — саммари в Markdown
- `{name}_summary.json` — структурированное саммари

Если в папке есть два файла с одинаковым именем, но разными расширениями (`call.wav` и `call.mp3`), команда завершается с ошибкой до обработки — чтобы не затирать результаты. Если отдельные файлы не удалось обработать, batch продолжает работу и в конце выводит счётчик `N succeeded, M failed`; exit code 1 при любых ошибках.

### По шагам

**Транскрибация:**
```bash
uv run recap transcribe meeting.wav
uv run recap transcribe call.wav -o call.txt -l en
```

**Саммари из готовой транскрипции:**
```bash
uv run recap summarize
uv run recap summarize call.txt -m brief
uv run recap summarize call.txt -m detailed -p openai --model gpt-4o
```

**JSON-вывод** (статусные сообщения идут в stderr, stdout — чистый JSON):
```bash
uv run recap summarize call.txt -f json
uv run recap summarize call.txt -f json > summary.json
```

### Опции

| Опция | Команды | Описание |
|---|---|---|
| `-o, --output PATH` | transcribe, summarize | Файл вывода |
| `-o, --output-dir PATH` | batch | Папка вывода (по умолчанию — папка с аудио) |
| `-l, --language TEXT` | transcribe, run, batch | Язык аудио (`ru`, `en`, …) |
| `-m, --mode TEXT` | summarize, run, batch | Режим: `brief` \| `medium` \| `detailed` \| `lecture` |
| `-f, --format TEXT` | summarize | Что печатать в stdout: `markdown` (по умолчанию) \| `json`. Оба файла пишутся в любом случае |
| `-p, --provider TEXT` | summarize, run, batch | Провайдер (см. таблицу выше) |
| `--model TEXT` | summarize, run, batch | Модель LLM (переопределяет config) |
| `--transcript PATH` | run | Путь для промежуточной транскрипции |
| `--summary PATH` | run | Путь для саммари |
| `-v, --verbose` | все | Показывать прогресс |

> **Breaking change:** флаг `-m` переназначен с `--model` на `--mode`. Для указания модели используйте `--model`.

### Ручная предобработка

```bash
uv run recap preprocess meeting.mp3 -o meeting.normalized.wav
```

Команда использует параметры из секции `preprocessing`, но выполняется всегда, даже если `preprocessing.enabled: false`. Поле `enabled` включает только автоматическую предобработку в `transcribe`, `run` и `batch`. Если `-o` не указан, файл сохраняется рядом с исходником как `{stem}.preprocessed.wav`.

### Автоматическая предобработка аудио

Опционально можно приводить входные файлы к стабильному WAV перед Whisper автоматически в командах `transcribe`, `run`, `batch`. Требует установленный `ffmpeg`.

```yaml
preprocessing:
  enabled: true
  sample_rate: 16000
  channels: 1
  loudness_normalization: true
  highpass_hz: 70
```

По умолчанию предобработка выключена (`enabled: false`) — `ffmpeg` при этом не требуется. При `enabled: true` и отсутствии `ffmpeg` команда завершается с понятной ошибкой. В пакетном режиме (`batch`) ошибка предобработки одного файла не прерывает обработку остальных.

Переменные среды: `RECAP_PREPROCESSING_ENABLED`, `RECAP_PREPROCESSING_SAMPLE_RATE`, `RECAP_PREPROCESSING_CHANNELS`, `RECAP_PREPROCESSING_CODEC`, `RECAP_PREPROCESSING_LOUDNESS_NORMALIZATION`, `RECAP_PREPROCESSING_TARGET_LUFS`, `RECAP_PREPROCESSING_TRUE_PEAK_DB`, `RECAP_PREPROCESSING_LOUDNESS_RANGE`, `RECAP_PREPROCESSING_HIGHPASS_HZ`, `RECAP_PREPROCESSING_KEEP_TEMP`.

## Десктоп-приложение

Кроме CLI, в репозитории есть десктоп-приложение (Tauri 2 + React) поверх того же Python-пайплайна.
Rust-слой запускает второй entry point — `recap-bridge` (`pyproject.toml`), — а вся логика остаётся
в `src/` и покрыта тестами. UI можно демонстрировать в браузере без Rust/GPU (встроенный mock-мост).

- Разработка фронтенда и запуск реального приложения: [`desktop/README.md`](desktop/README.md).
- Портативная сборка для Windows (распаковал и запустил `Recap.exe`, Python на машине не нужен):
  [`docs/portable-build.md`](docs/portable-build.md).
- Архитектура, контракт моста и спека: [`docs/desktop-tauri-spec.md`](docs/desktop-tauri-spec.md),
  [`docs/desktop-bridge-contract.md`](docs/desktop-bridge-contract.md).

## Решения, техдолг и развитие

- Принятые архитектурные решения: [`docs/adr/`](docs/adr/README.md).
- Актуальный технический долг и известные проблемы: [`docs/issues/roadmap.md`](docs/issues/roadmap.md).
- Предложения по развитию продукта: [`docs/proposals/README.md`](docs/proposals/README.md).
- Датированные снимки ревью и ручной проверки: [`docs/reviews/`](docs/reviews/).

Issue описывает разрыв относительно уже принятого поведения; новая возможность является proposal,
а не issue. Статусы живут только в индексах соответствующих списков.

## Telegram Markdown

Саммари форматируется в **Telegram Markdown v1** (`parse_mode="Markdown"`):

| Элемент | Синтаксис |
|---|---|
| Жирный | `*текст*` |
| Курсив | `_текст_` |
| Код | `` `код` `` |
| Ссылка | `[текст](url)` |

**Ограничения:** Telegram Markdown v1 не поддерживает экранирование спецсимволов. Если в тексте встречаются несбалансированные `_` или `` ` `` (например, в технических терминах), Telegram может не принять сообщение. Промпт явно запрещает модели использовать `_` для форматирования, поэтому на практике это редко. Для полной совместимости со спецсимволами в будущем предполагается переход на MarkdownV2.

## Приватность

Транскрипт встречи отправляется в LLM только для саммари. Важно понимать, куда он уходит:

| Провайдер | Данные |
|---|---|
| `ollama`, `lm-studio`, `vllm` | Остаются локально — не покидают машину |
| `openai`, `xai` или внешний `base_url` | Отправляются на внешний сервер |

При использовании внешнего endpoint CLI выводит предупреждение в stderr. Чтобы его отключить, добавьте в `config.yaml`:

```yaml
privacy_ack: true
```

Или через переменную среды: `RECAP_PRIVACY_ACK=true`.

> **Breaking change:** схема `config.yaml` стала вложенной (`transcription` / `summarization`, в каждой — `model`). Старые плоские ключи и старые плоские `RECAP_*` переменные не поддерживаются. API-ключ задаётся только через `summarization.model.api_key` или `RECAP_SUMMARIZATION_MODEL_API_KEY` — неявного fallback на `OPENAI_API_KEY` больше нет.

## Разработка

```bash
uv sync --group dev
uv run pytest -v
```

**Линтер и форматирование:**
```bash
uv run ruff check src/        # проверка стиля
uv run ruff check src/ --fix  # авто-исправление
uv run ruff format src/       # форматирование кода
```

**Типизация:**
```bash
uv run mypy src/
```
