# Ревью проекта recap — индекс

Последний запуск: **2026-07-05** ([снапшот](reviews/2026-07-05.md); предыдущий —
[2026-07-02](reviews/2026-07-02.md), все его 40 issue закрыты). Статусы и решения — в
[roadmap.md](roadmap.md) (единственный источник статусов; файлы issue статус не несут).

## Сводка (открытые issue запуска 2026-07-05)

| Severity | Кол-во |
|----------|--------|
| critical | 0 |
| high     | 2 |
| medium   | 13 |
| low      | 17 |
| **всего** | **32** |

Инструментальные проверки на дату запуска: ruff/mypy — чисто; **pytest — 1 failed** (SEC-005),
349 passed; npm lint/test/build — зелёные; cargo check/clippy — чисто; npm audit — 0.

## Начать отсюда (severity × effort)

1. [SEC-005](issues/SEC-005.md) — pytest печатает живой API-ключ из env, сьют красный при
   документированной настройке → **conftest-скраббер + ротация ключа сегодня**
2. [AGENT-009](issues/AGENT-009.md) — AGENTS.md активно запрещает существующую унификацию CLI:
   следующий агент может «починить» код назад
3. [ARCH-006](issues/ARCH-006.md) — round-trip render↔parse ломается на `\n` в элементе списка —
   тихая порча саммари при «Сохранить»/экспорте (репро в issue)
4. [CODE-008](issues/CODE-008.md) — регрессия: duration-probe удалён, прогресс транскрибации
   снова молчит на видео-входах пользователя
5. [REL-009](issues/REL-009.md) + [SEC-006](issues/SEC-006.md) — сетевые загрузки: Ollama-pull
   виснет навсегда без таймаута; CUDA-wheels без sha256
6. Пакет AGENT-010…013 — память/чеклист/QA-долг: дешёвые правки, убирающие ложную карту среды

## Issue по категориям

### Архитектура (ARCH)
- medium [ARCH-005](issues/ARCH-005.md) — resummarize игнорирует cancel_flag: «Остановить» не работает в режимах суммаризации
- medium [ARCH-006](issues/ARCH-006.md) — round-trip render↔parse не точен (`\n` в элементе списка)

### Качество кода (CODE)
- medium [CODE-008](issues/CODE-008.md) — регрессия duration-probe: прогресс молчит при duration=0
- low [CODE-009](issues/CODE-009.md) — SUMMARY_JSON_SCHEMA — мёртвый код
- low [CODE-010](issues/CODE-010.md) — мок bridge.ts: отмена завершается success
- low [CODE-011](issues/CODE-011.md) — serve() дублирует обвязку _streaming()
- low [CODE-012](issues/CODE-012.md) — stepsForStatus красит не те шаги (hypothesis)

### Зависимости (DEP)
- low [DEP-005](issues/DEP-005.md) — пины CUDA: `>=` в pyproject против `==` в cuda_support
- low [DEP-006](issues/DEP-006.md) — PyInstaller не задекларирован и не запинен

### Надёжность (REL)
- medium [REL-009](issues/REL-009.md) — Ollama-pull: timeout=None, вечное зависание, глухая отмена
- medium [REL-010](issues/REL-010.md) — CUDA-загрузка не смотрит на реальное GPU (2 ГБ впустую / тихий CPU)
- low [REL-011](issues/REL-011.md) — портативный ffmpeg вне зоны поиска моста
- low [REL-012](issues/REL-012.md) — UTF-8-фикс не покрывает stdin
- low [REL-013](issues/REL-013.md) — экспорт падает целиком на битом .json
- low [REL-014](issues/REL-014.md) — ротация лога при живом worker (hypothesis)

### Безопасность (SEC)
- **high** [SEC-005](issues/SEC-005.md) — живой ключ в выводе pytest; сьют не изолирован от env
- medium [SEC-006](issues/SEC-006.md) — CUDA-wheels без sha256-верификации
- medium [SEC-007](issues/SEC-007.md) — нескоуплённая запись из webview (save_summary, traversal в export)
- low [SEC-008](issues/SEC-008.md) — zip-slip в _extract_dlls
- low [SEC-009](issues/SEC-009.md) — pull_model доверяет base_url из webview (SSRF)

### Производительность (PERF)
- low [PERF-003](issues/PERF-003.md) — распаковка CUDA: DLL целиком в RAM, cancel не опрашивается

### Конвенции (CONV)
- low [CONV-002](issues/CONV-002.md) — known-first-party дрейфует второй раз — удалить список

### Документация (DOC)
- medium [DOC-003](issues/DOC-003.md) — контракт моста снова отстал (download, 3 команды)
- medium [DOC-004](issues/DOC-004.md) — lecture/расширения/portable невидимы в README и `--help`
- low [DOC-005](issues/DOC-005.md) — доковая пыль (шапка spec, «338 tests», step-комментарий)

### Агентская система (AGENT)
- **high** [AGENT-009](issues/AGENT-009.md) — AGENTS.md материально ложен (запрещает существующую унификацию)
- medium [AGENT-010](issues/AGENT-010.md) — память desktop-tauri-mvp.md противоречит коду
- medium [AGENT-011](issues/AGENT-011.md) — runtime-знание заперто в памяти; AGENTS.md утверждает обратное
- medium [AGENT-012](issues/AGENT-012.md) — checklist-документ — завершённое ТЗ под видом живого
- medium [AGENT-013](issues/AGENT-013.md) — долг ручной Windows-QA нигде не накапливается
- low [AGENT-014](issues/AGENT-014.md) — allowlist не версионируется вопреки замыслу
- low [AGENT-015](issues/AGENT-015.md) — allow-паттерны и составные вызовы (hypothesis)

## Сильные стороны

Калибровка: 40 issue первого ревью закрыты за один день с честными отметками верификации; новые
находки — почти целиком про код последних трёх дней, а не про разрушение старого.

1. **Контур review → roadmap → burndown замкнут и работает.** Все 40 прежних issue доведены до
   `done` с датированными отметками и журналом решений; статусы принадлежат человеку.
2. **Правило честной верификации соблюдается делом.** Коммит `24964d9` прямо пишет «UNVERIFIED
   scaffolding… The first Windows run is the real integration test»; roadmap фиксирует
   «drag-in-app вручную не проверял». Нарушений AGENTS.md после 02.07 не найдено (uv — ни разу,
   git — только по запросу).
3. **Новые сетевые модули изолированы правильно.** `cuda_support`/`ollama_support` — pure stdlib,
   без импортов providers/config, подключаются лениво; `recap --help` по-прежнему мгновенный;
   дизайн «сентинел последним» в CUDA-кэше корректно переживает kill/cancel/переполнение диска.
4. **Гигиена секретов в коде держится.** `_settings_to_dict` — только маска; `save_settings`
   вычищает ключ; история — только пути; XSS в экспортном HTML нет (`html.escape` везде).
   (Единственная утечка — через тестовый вывод, SEC-005, источник вне продакшен-кода.)
5. **Инварианты прошлого ревью не разрушены.** Атомарные записи + межпроцессный лок истории;
   кооперативная отмена run_recap; worker самозавершается по EOF и убивается на Exit;
   partial_success-контракт цел; integration-тесты мокают только фабрику.
6. **Практика handoff-промпта.** Сформулированная агентом постановка проблемы (симптом, путь
   события, отработанные гипотезы) позволила свежей сессии решить многоитерационный баг с
   первого захода — кандидат в повторяемую практику.
