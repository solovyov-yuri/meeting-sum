# Ревью проекта recap — индекс

Последний запуск: **2026-07-02** ([снапшот](reviews/2026-07-02.md)). Статусы и решения — в
[roadmap.md](roadmap.md) (единственный источник статусов; файлы issue статус не несут).

## Сводка

| Severity | Кол-во |
|----------|--------|
| critical | 0 |
| high     | 8 |
| medium   | 17 |
| low      | 15 |
| **всего** | **40** |

Инструментальные проверки на дату запуска: ruff — чисто, mypy — чисто, pytest — 298 passed.

## Начать отсюда (severity × effort)

1. [SEC-001](issues/SEC-001.md) — живой API-ключ в открытом виде в `config.yaml` → **ротировать сегодня**
2. [REL-001](issues/REL-001.md) — `UnicodeDecodeError` роняет summarize сырым трейсбэком
3. [REL-004](issues/REL-004.md) — десктоп отклоняет `.mp4`, реальный формат записей пользователя
4. [ARCH-002](issues/ARCH-002.md) — отмена в десктопе: kill вместо контракта, потеря истории/транскрипта
5. [AGENT-002](issues/AGENT-002.md) + [AGENT-006](issues/AGENT-006.md) — обновить CLAUDE.md/AGENTS.md (desktop-слой + правило честной верификации)
6. [ARCH-001](issues/ARCH-001.md) — дублированный пайплайн cli.py ↔ workflows.py (самая дорогая структурная проблема)

## Issue по категориям

### Архитектура (ARCH)
- **high** [ARCH-001](issues/ARCH-001.md) — пайплайн продублирован cli.py ↔ workflows.py, поведение уже расходится
- **high** [ARCH-002](issues/ARCH-002.md) — отмена: kill процесса вместо кооперативной; мёртвый CancelCheck
- medium [ARCH-003](issues/ARCH-003.md) — `output_formats` — мёртвый вход контракта
- medium [ARCH-004](issues/ARCH-004.md) — stderr моста в null: технических логов не существует

### Качество кода (CODE)
- medium [CODE-001](issues/CODE-001.md) — хардкод путей вывода рядом с аудио; молчаливая перезапись
- medium [CODE-005](issues/CODE-005.md) — test_connection смешивает черновик и сохранённый конфиг
- low [CODE-002](issues/CODE-002.md), [CODE-003](issues/CODE-003.md), [CODE-004](issues/CODE-004.md), [CODE-006](issues/CODE-006.md), [CODE-007](issues/CODE-007.md)

### Зависимости (DEP)
- medium [DEP-001](issues/DEP-001.md) — ESLint 8 EOL; medium [DEP-003](issues/DEP-003.md) — безусловные CUDA-wheels
- low [DEP-002](issues/DEP-002.md), [DEP-004](issues/DEP-004.md)

### Надёжность (REL)
- **high** [REL-001](issues/REL-001.md) — UnicodeDecodeError мимо error boundary
- **high** [REL-004](issues/REL-004.md) — десктоп отклоняет .mp4
- medium [REL-002](issues/REL-002.md) — ffmpeg без -nostdin/timeout; medium [REL-003](issues/REL-003.md) — мигающая консоль (hypothesis)
- low [REL-005](issues/REL-005.md), [REL-006](issues/REL-006.md), [REL-007](issues/REL-007.md), [REL-008](issues/REL-008.md)

### Безопасность (SEC)
- **high** [SEC-001](issues/SEC-001.md) — живой API-ключ в config.yaml (не в git — проверено)
- medium [SEC-002](issues/SEC-002.md) — CSP null; medium [SEC-003](issues/SEC-003.md) — нескоуплённые файловые IPC; medium [SEC-004](issues/SEC-004.md) — скрытый env-fallback ключа (hypothesis)

### Производительность (PERF)
- medium [PERF-001](issues/PERF-001.md) — перезагрузка Whisper-модели на каждый запуск
- low [PERF-002](issues/PERF-002.md) — последовательные чанки

### Конвенции (CONV)
- low [CONV-001](issues/CONV-001.md) — устаревший known-first-party в ruff

### Документация (DOC)
- medium [DOC-001](issues/DOC-001.md) — контракт моста без 4 реализованных команд
- low [DOC-002](issues/DOC-002.md) — README без упоминания десктопа

### Агентская система (AGENT)
- **high** [AGENT-001](issues/AGENT-001.md) — скилл project-review без references/assets, 3 копии
- **high** [AGENT-002](issues/AGENT-002.md) — CLAUDE.md/AGENTS.md устарели (desktop-слой невидим)
- **high** [AGENT-006](issues/AGENT-006.md) — ложная верификация; правила нет в checked-in файлах
- medium [AGENT-003](issues/AGENT-003.md), [AGENT-004](issues/AGENT-004.md), [AGENT-005](issues/AGENT-005.md), [AGENT-007](issues/AGENT-007.md)
- low [AGENT-008](issues/AGENT-008.md)

## Сильные стороны

Ревью откалибровано: проект в целом дисциплинированный, находки — про рост, а не про разруху.

1. **Атомарные записи — реально везде.** Все персистентные записи в CLI/workflows/bridge идут через `write_text_atomic` (`src/utils.py:7`); `Path.write_text` в продакшен-путях отсутствует.
2. **Инвариант «транскрипт до LLM» доведён до конца.** `run_one_file` сохраняет транскрипт до суммаризации, `partial_success` доходит до UI-баннера «Повторить суммаризацию», `resummarize_one` переиспользует транскрипт с диска — длинные встречи не транскрибируются повторно.
3. **Гигиена секретов в десктопе по контракту.** Ключи только в OS-keychain (`secrets_store.py`), наружу — только маскированный boolean; из YAML ключ вычищается перед записью; история хранит только пути/метаданные. `config.yaml` и записи встреч в `data/` не закоммичены (история git проверена).
4. **Rust-слой сознательно «тупой».** 12 тонких Tauri-команд поверх юнит-тестированного Python-моста; единая точка интеграции `getBridge()` с browser-моком — весь UI демонстрируется без Rust и GPU.
5. **Строгая валидация конфига с отличными ошибками.** Неизвестные ключи отклоняются с точным dotted-path; настройки из UI прогоняются через `Settings.load` перед сохранением.
6. **Тесты пропорциональны и уважают границы.** ~4,000 строк тестов на ~2,500 строк src; integration мокает только фабрику; ruff/mypy/pytest — зелёные. Бонус: системный промпт содержит защиту от prompt-injection в `<transcript>`.
7. **Дисциплина делегирования.** Desktop MVP делался по заранее написанным спекам с явными критериями приёмки; баг-репорты пользователя — точные file:line. Auto-memory честно фиксирует, что НЕ было проверено.
