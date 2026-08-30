---
id: AGENT-001
title: "Скилл project-review: отсутствуют все 5 файлов references/assets; три расходящиеся копии скилла"
category: AGENT
severity: high
effort: small
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-02
review_last_seen: 2026-07-02
depends_on: []
locations:
  - path: .claude/skills/project-review/SKILL.md
    anchor: "references/severity-effort.md"
---

# AGENT-001: Скилл project-review неполон и растроен

## Проблема

`SKILL.md` ссылается на `references/severity-effort.md`, `references/agent-system-review.md`,
`assets/issue-template.md`, `assets/roadmap-template.md`, `assets/index-template.md` («Definitions
in references/severity-effort.md — read it before», «This is not optional filler»), но ни один из
этих файлов не существует ни в проектной копии, ни в
`/mnt/c/Users/solov/.claude/skills/project-review/`. WSL-домашняя `/home/samogonn/.claude/skills/`
пуста, при этом сегодняшний запуск объявил базовым каталогом именно её. Итого: три потенциальные
локации скилла, файлы методологии недостижимы, плюс `SKILL.md:Zone.Identifier`-мусор.

Данный отчёт (2026-07-02) построен по импровизированным шаблонам, восстановленным из описаний в
SKILL.md — их можно сохранить как канонические assets.

## Почему это важно

Ядро методологии скилла — рубрика severity/effort, чек-лист AGENT-ревью и шаблоны вывода —
недоступно; каждый запуск импровизирует формат, что подрывает главное обещание скилла:
идемпотентные повторные запуски со стабильными ID и merge-правилами.

## Варианты решения

1. **Рекомендуется:** восстановить/написать `references/` и `assets/` рядом с SKILL.md в **проектной** копии (скилл проектный); удалить копию в Windows-home; убрать Zone.Identifier. За основу шаблонов взять фактический формат `.agent-review/` этого запуска.
2. Разобраться с двойным `.claude`-home (см. [[AGENT-004]]) до выбора канонической локации.

## Как проверить исправление

`find .claude/skills/project-review` показывает SKILL.md + 2 references + 3 assets; следующий запуск `/project-review` не импровизирует форматы.

## Связанные

[[AGENT-004]], [[AGENT-008]].
