# 📋 Master каталог задач

Задачи группируются по фазам. Префикс = фаза, номер сквозной внутри префикса (gaps разрешены).

Легенда: ✅ done · 🛠 in progress · 📝 todo · ⏸ blocked

---

## Phase A — Критичные дефекты (P0/P1)

_Пусто — критичных багов нет._

---

## Phase B — Исправленные баги (история)

### B-01 · Модель не переключается при выборе через `/model`
Пользователь говорил `/model gpt-oss-20b`, бот отвечал «unavailable».
→ Root cause: модель не была запуллена на Lemonade.
→ Fix: валидация через `list_models()` до переключения + понятное сообщение.
✅ Commit 760b9ad · 2026-04-09

### B-02 · Inline keyboard не показывала смену выбора
После тапа на кнопку надпись «Current model» не обновлялась.
✅ Commit 609e241 · 2026-04-10

### B-03 · После тапа на inline button не было подтверждения
Клавиатура обновлялась, но не было message «Switched».
✅ Commit b0b0dd0 · 2026-04-10

---

## Phase C — Технический долг

### C-01 📝 Привести в соответствие Ollama / Lemonade конфигурацию
`app/config.py` default = `http://ollama:11434`, но `.env.example` = `http://lemonade:8000/api`, docker-compose сервис `lemonade`, README упоминает Ollama. Разночтение между default / .env / README.
Branch: `feature/TD/BOT-14`
См. [legacy-warning.md § 1](legacy-warning.md#1-ollama--lemonade-несогласованность)

### C-02 📝 Обновить Makefile pull-models под Lemonade
Сейчас таргет `pull-models` вызывает `docker compose exec ollama ollama pull`. Сервис `ollama` отсутствует.
См. [legacy-warning.md § 2](legacy-warning.md#2-makefile-pull-models-сломан)

### C-03 📝 Кеш `list_models()`
HTTP запрос к LLM серверу на каждый `/models` и переключение. Добавить TTL-кеш на 60s.
См. [discuss.md § 6](discuss.md#6-model-list-caching)

---

## Phase D — Фичи

### D-01 ✅ Inline keyboard model selection
→ Commit f5de296 · 2026-04-10

### D-02 ✅ Лог переключения модели в чат
`previous → new` отдельным сообщением.
→ Commits 609e241, b0b0dd0 · 2026-04-10

### D-03 📝 Persistent per-user model selection
JSON file на диске. См. [discuss.md § 1](discuss.md#1-persistence-для-per-user-selected-model).

### D-04 🛠 Dialog history — persistent YAML per-user
Псевдо-память: хранить историю диалога в `data/history/{user_id}.yaml`, отправлять в LLM полную историю + новое сообщение. Sliding window через env `HISTORY_MAX_MESSAGES` (default 20, 0 = без лимита). Новая команда `/reset`.
Branch: `feature/BAU/BOT-D04`
→ [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)
См. [discuss.md § 2](discuss.md#2-dialog-history) (решение принято 2026-04-15).
