---
id: AGENT-010
title: "Auto-memory desktop-tauri-mvp.md активно противоречит текущей архитектуре (унификация CLI, keyring, cargo, число тестов)"
category: AGENT
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: /home/samogonn/.claude/projects/-mnt-c-Users-solov-projects-job-inno-recap/memory/desktop-tauri-mvp.md
    anchor: "cli.py kept its own command bodies"
---

# AGENT-010: Устаревшая память подгружается в каждую сессию как «знание»

## Проблема

Файл памяти от 2026-06-19 содержит четыре утверждения, опровергнутых кодом/средой:

1. «cli.py kept its own command bodies/messages…» — опровергнуто унификацией ARCH-001 (02.07):
   CLI идёт через `run_one_file`/`resummarize_one`.
2. «`keyring` is in pyproject deps but not installed in the venv» — `import keyring` в текущем
   venv проходит.
3. «no Rust toolchain (cargo/rustc) in this env» — опровергнуто: AGENTS.md документирует рабочий
   `cargo.exe check/clippy` из WSL.
4. «294 tests» — сейчас 350.

## Почему это важно

Auto-memory загружается в каждую сессию; агент, опирающийся на неё, будет уверенно утверждать
ложные факты — тот же класс ошибок, что и [[AGENT-009]], только через другой канал. (Ревью-скилл
сам предупреждает: воспоминания отражают момент записи — но противоречащие детали лучше убирать,
чем оговаривать.)

## Варианты решения

1. **(Рекомендуется)** Переписать файл: оставить актуальную схему слоёв, убрать четыре устаревших
   утверждения и снимок верификации.
2. Удалить файл целиком (layout уже есть в AGENTS.md).

## Как проверить исправление

Перечитать файл: ни одно утверждение не противоречит `src/cli.py` (routing через workflows) и
разделу Verification boundary в AGENTS.md.

## Связанные

[[AGENT-009]], [[AGENT-011]].
