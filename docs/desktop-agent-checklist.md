# Чеклист для агента: desktop MVP

## 1. Перед началом

- Прочитать `AGENTS.md`.
- Прочитать это ТЗ:
  - `docs/desktop-tauri-spec.md`;
  - `docs/desktop-ux.md`;
  - `docs/desktop-bridge-contract.md`.
- Проверить текущий `src/config.py`, `src/cli.py`, `src/providers/factory.py`, `src/preprocessing.py`.
- Не делать git commit/branch без явной просьбы пользователя.

## 2. Backend work

- Вынести reusable workflow из `src/cli.py` в `src/workflows.py`.
- Сохранить CLI behavior.
- Добавить structured progress events.
- Реализовать partial success: transcript сохранен, LLM failed.
- Добавить bridge-friendly facade.
- Не писать secrets в config.
- Не ломать strict config validation.
- Все записи делать через `write_text_atomic()`.

## 3. Frontend work

- Создать Tauri app.
- Реализовать layout:
  - sidebar;
  - main workspace;
  - inspector.
- Сделать русский UI.
- Реализовать выбор файла и drag-and-drop.
- Реализовать run flow.
- Реализовать tabs:
  - transcript;
  - summary;
  - log.
- Summary editable.
- Transcript readonly.
- Реализовать Settings sections.
- Реализовать History JSON list.
- Реализовать export/copy/open folder.
- Реализовать error states.

## 4. UX acceptance

- Нет landing page.
- Нет marketing hero.
- Нет nested cards.
- Нет декоративных gradients/orbs/blobs.
- UI помещается на desktop viewport без overlap.
- Кнопки и controls имеют понятные disabled/loading states.
- Ошибки написаны по-русски.
- API key masked.

## 5. Manual QA

- Запуск приложения.
- Выбор audio file.
- Успешный run на коротком файле или mock provider.
- LLM failure показывает partial success.
- Summary редактируется.
- Copy работает.
- Export создает Telegram/plain/JSON.
- History обновляется.
- Settings сохраняются.
- API key сохраняется и удаляется.
- CLI команды продолжают работать.

## 6. Automated checks

Python:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check src/
.venv\Scripts\mypy.exe src/
```

Frontend, если добавлен:

```powershell
npm run lint
npm run test
npm run build
```

Tauri:

```powershell
npm run tauri dev
npm run tauri build
```

Если какая-то проверка не может быть выполнена локально, агент должен явно указать причину.
