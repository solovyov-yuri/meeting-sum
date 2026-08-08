---
id: AGENT-002
title: "CLAUDE.md/AGENTS.md устарели: desktop-слой (~1000 строк src) невидим, правило «единственный error boundary» ложно"
category: AGENT
severity: high
effort: small
status: proposed
evidence: confirmed
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: CLAUDE.md
    anchor: "cli.py is the *only* place that catches exceptions"
  - path: src/workflows.py
    anchor: "def run_one_file"
    line_hint: 174
  - path: src/desktop_bridge.py
    anchor: "# noqa: BLE001 - boundary"
    line_hint: 461
---

# AGENT-002: Карта архитектуры в CLAUDE.md/AGENTS.md устарела и вводит в заблуждение

## Проблема

Архитектурное дерево в CLAUDE.md/AGENTS.md перечисляет только «старые» модули. Отсутствуют:
`workflows.py` (18K, переиспользуемый конвейер), `desktop_bridge.py` (20K, JSON-фасад + entry
point `recap-bridge` из `pyproject.toml:24`), `secrets_store.py` (keyring), и весь каталог
`desktop/` (Tauri/React). Правило «`cli.py` is the *only* place that catches exceptions» теперь
фактически ложно — boundary три: CLI, `workflows.run_one_file` (ловит на границах шагов, возвращает
`RunResult`), `desktop_bridge._streaming`/`main` (`# noqa: BLE001 - boundary`).

Единственное точное описание desktop-слоя живёт в локальной авто-памяти агента
(`memory/desktop-tauri-mvp.md`) — не в репозитории, невидимо для Codex и других машин.

Уточнить заодно: «one test_*.py per module» (нет test_models/test_prompts — тривиальные модули) и
скоуп «mocks only at factory boundary» (в pyproject он ограничен integration-тестами, CLAUDE.md
читается как правило для всего сьюта; `tests/test_cli.py:92-98` патчит глубже — это ок для
юнит-уровня).

## Почему это важно

CLAUDE.md — операционный контракт для агентов. Треть src невидима; агент, «чинящий» workflows под
устаревшее правило (пусть исключения пролетают), сломает контракт partial_success моста.

## Варианты решения

1. **Рекомендуется:** обновить дерево (+workflows, +desktop_bridge, +secrets_store, +desktop/), переписать правило: «boundaries: cli.py для CLI; desktop_bridge.main/_streaming и workflows.run_one_file для десктопа; провайдеры и хелперы пропускают исключения». Добавить `recap-bridge` в команды и фронтенд-проверки (`npm run lint|test|build`, node.exe в `/mnt/c/Program Files/nodejs`, tauri/cargo — только Windows-сторона). Портировать содержимое memory-файла — он уже написан.
2. Минимум: абзац «Desktop backend» со ссылкой на docstring `workflows.py`, где исправленные правила уже сформулированы верно.

## Как проверить исправление

Каждый файл `src/*.py` упомянут в дереве; правило error boundary соответствует трём фактическим boundary; про desktop/ есть раздел.

## Связанные

[[AGENT-003]], [[AGENT-007]], [[ARCH-001]].
