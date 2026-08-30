---
id: CODE-008
title: "Регрессия: da9d474 удалил WAV-duration-probe из 3dd5381 — прогресс транскрибации снова молчит при info.duration=0 (реальный вход пользователя)"
category: CODE
severity: medium
effort: quick-win
status: proposed
evidence: confirmed
source: review
review_first_seen: 2026-07-05
review_last_seen: 2026-07-05
depends_on: []
locations:
  - path: src/providers/whisper.py
    anchor: "Whisper reported no audio duration"
    line_hint: 127
---

# CODE-008: Откат фикса прогресса для аудио без duration

## Проблема

Коммит `3dd5381` (02.07) добавил `_probe_wav_duration()` и `duration = info.duration or
_probe_wav_duration(audio)` — с обоснованием в сообщении коммита: **на реальном входе
пользователя** (видео → препроцессированный WAV) faster-whisper вернул `info.duration=0`, и за
весь 7,5-минутный запуск не ушло ни одного progress-события. Следующий коммит `da9d474` («stop
rich Progress swallowing…») этот probe удалил вместе с его тестами (52 строки), никак не
мотивировав удаление в сообщении. Текущий код лишь логирует warning и оставляет прогресс немым:

```python
duration = info.duration
if on_progress is not None and not duration:
    logger.warning("Whisper reported no audio duration — transcription progress %% unavailable.")
```

## Доказательства

`git log --oneline -- src/providers/whisper.py`: `3dd5381` → `da9d474`; текущий
`src/providers/whisper.py` — probe отсутствует (проверено 2026-07-05). Сообщение `3dd5381`
фиксирует, что случай наблюдался на фактическом входе пользователя.

## Почему это важно

Рубрика ревью: баг на реально наблюдавшемся входе пользователя. Для mp4/mkv-записей (поддержаны в
`AUDIO_EXTENSIONS`) кольцо транскрибации крутится без процентов весь самый долгий этап — прогресс
был главным итогом CODE-006. Это единственная найденная регрессия ранее внесённых фиксов.

## Варианты решения

1. **(Рекомендуется)** Вернуть `_probe_wav_duration()` и `or _probe_wav_duration(audio)` вместе с
   тестами из `git show 3dd5381` — probe совместим с текущей структурой `transcribe()`
   (Rich-часть, ради которой был da9d474, не пострадает).
2. Альтернатива: при `duration==0` считать прогресс по `s.end / probed_total` только когда
   `on_progress is not None` (микрооптимизация, тот же probe).

## Как проверить исправление

Восстановленные тесты из `3dd5381 -- tests/test_whisper.py` зелёные; вручную — прогресс на аудио,
извлечённом из видео (GPU-машина).

## Связанные

[[CODE-006]] — исходное появление percent-прогресса.
