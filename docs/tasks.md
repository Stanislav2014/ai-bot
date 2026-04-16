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

### C-01 ✅ Привести в соответствие Ollama / Lemonade конфигурацию
Переименованы `ollama_base_url` → `llm_base_url`, `.env.example` + `tests/conftest.py` обновлены, docker-compose.yml переведён на Lemonade-сервис, `app/llm/client.py` использует `/v1/models` вместо `/api/tags`, добавлен `lemonade/Dockerfile`.
→ commit `debb155` на master · 2026-04-15
Частично закрывает [legacy-warning.md § 1](legacy-warning.md#1-ollama--lemonade-несогласованность). Остались: README.md упоминания Ollama, Makefile `pull-models` (см. C-02).

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

### D-04 ✅ Dialog history — persistent YAML per-user
Псевдо-память: `data/history/{user_id}.yaml`, sliding window (env `HISTORY_MAX_MESSAGES`, default 20), команда `/reset`. System prompt prepend-ится из кода, не хранится в файле.
→ [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)
Branch: `feature/BAU/BOT-D04` · merged 2026-04-15

### D-05 ✅ Context char limit — второй safeguard
Кап по суммарной длине истории (`HISTORY_MAX_CHARS`, default 8000). Работает поверх `HISTORY_MAX_MESSAGES`. FIFO-trim защищает от одной длинной простыни, переполняющей context window. Last-message protected from drop.
Branch: `feature/BAU/BOT-D05` · merged 2026-04-15 · 15/15 tests green
→ [tasks/D-05_CONTEXT_CHAR_LIMIT.md](tasks/D-05_CONTEXT_CHAR_LIMIT.md)

### D-06 ✅ History summarization — умная обрезка через LLM
Summarizer класс: при `len > HISTORY_SUMMARIZE_THRESHOLD` (default 5) старые сообщения заменяются single summary-system-message через LLM-запрос; последние `HISTORY_KEEP_RECENT` (default 2) сохраняются raw. Fail-safe. D-04/D-05 — fallback.
Branch: `feature/BAU/BOT-D06` · merged 2026-04-15 · 24/24 tests green
→ [tasks/D-06_HISTORY_SUMMARIZATION.md](tasks/D-06_HISTORY_SUMMARIZATION.md)

### D-07 ✅ System prompt — configurable persona
Env `SYSTEM_PROMPT` (default: русский программистский persona) вместо hardcoded `"You are a helpful assistant..."`. Инъекция в `BotHandlers.__init__`. Module-level константа удалена.
Branch: `feature/BAU/BOT-D07` · code complete 2026-04-15 · 24/24 tests green
→ [tasks/D-07_SYSTEM_PROMPT.md](tasks/D-07_SYSTEM_PROMPT.md)
