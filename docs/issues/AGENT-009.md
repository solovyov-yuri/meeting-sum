---
id: AGENT-009
title: "AGENTS.md материально ложен: запрещает существующую унификацию CLI↔workflows, карта src/ без двух модулей, режимы без lecture"
category: AGENT
severity: high
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: AGENTS.md
    anchor: "The CLI does **not** route through `workflows.run_one_file`"
  - path: src/cli.py
    anchor: "run_one_file"
    line_hint: 378
  - path: AGENTS.md
    anchor: "src/"
---

# AGENT-009: Канонический агентский контракт описывает несуществующий код

## Проблема

Три материально ложных утверждения в `AGENTS.md` (канонический контракт, который каждый агент
загружает при старте):

1. **Инвертированное правило.** «Key design rules» утверждают: «The CLI does **not** route through
   `workflows.run_one_file` … This divergence is intentional … do not "unify" it without an
   explicit i18n + output-semantics decision from the owner». Но владелец это решение **принял
   02.07** (roadmap, ARCH-001: «решение пользователя: унифицировать, расхождения не нужны»), и
   код унифицирован: `cli.py` `run`/`batch` → `run_one_file`, `summarize` → `resummarize_one`;
   сообщения пайплайна русские, CLI пишет `.txt`+`.json`. Правило прямо запрещает текущее
   состояние кода и описывает несуществующие свойства («CLI keeps English messages»).
2. **Карта src/ неполна:** `cuda_support.py` и `ollama_support.py` (два новых модуля с сетевым
   I/O) в дереве отсутствуют — `ls src/` даёт 15 модулей, карта перечисляет 13.
3. **Режимы:** «`summarization.mode`: `brief` | `medium` | `detailed`» — без `lecture`, который
   уже в `SUMMARY_MODES`, `config.yaml.example` и UI.

## Доказательства

Текст AGENTS.md (загружается в каждую сессию) против `src/cli.py:181,322,378` и `ls src/`;
решение владельца — запись «2026-07-02 — ARCH-001 — done» в `.agent-review/roadmap.md`
(проверено 2026-07-05). Дрейф возник в тот же день, что и фикс: коммит `0c48afa` унифицировал
CLI, а правило, добавленное коммитом `2a44c24` несколькими часами раньше, не сняли; docs-sync
`b42e9dd` (03.07) его тоже не тронул.

## Почему это важно

Это рецидив [[AGENT-002]] в худшей форме: не пробел, а **активный запрет корректного состояния**.
Следующий агент, чтящий контракт, может «починить» код обратно (раздублировать пайплайн) или
отказаться от корректных правок, сославшись на правило. По рубрике ревью ложный instruction-файл
— high.

Системная причина обоих рецидивов (этого и [[DOC-003]]/[[DOC-004]]): обновление
AGENTS.md/контрактов не входит в definition-of-done изменения — стоит добавить в AGENTS.md
короткое правило «правишь поведение, описанное в AGENTS.md/docs — правь документ в том же
коммите».

## Варианты решения

1. **(Рекомендуется)** Переписать пункт: CLI — тонкая обёртка над
   `run_one_file`/`resummarize_one`; отличия — приём флагов и вывод (`-f json` отдаёт `.json` в
   stdout); упоминание ARCH-001 как активного запрета убрать. Добавить `cuda_support.py` и
   `ollama_support.py` в карту, `lecture` — в список режимов. Плюс однострочное
   definition-of-done-правило про синхронное обновление доков.
2. Если унификация была ошибкой — откатить `0c48afa` (не рекомендуется: решение владельца
   зафиксировано, тесты перестроены).

## Как проверить исправление

`git grep 'does \*\*not\*\* route' AGENTS.md` пуст; карта src/ совпадает с `ls src/`; `lecture` в
списке режимов; в свежей сессии агент, спрошенный «как CLI связан с workflows», отвечает верно.

## Связанные

[[AGENT-002]] — прошлый дрейф того же файла; [[ARCH-001]] — источник решения; [[DOC-003]],
[[DOC-004]] — та же системная причина.
