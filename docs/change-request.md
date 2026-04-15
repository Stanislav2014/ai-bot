# Change Request — Sprint 1 (2026-04-15)

> 📋 Зеркало текущего спринта: каждая задача, которая находится в [current-sprint.md](current-sprint.md), имеет блок здесь. При merge задачи запись **не удаляется** — обновляется статус. Чистится только при закрытии спринта (архивации в task spec history).

---

## D-04 · Dialog history — persistent YAML per-user

| Поле | Значение |
|------|----------|
| **Task ID** | `D-04` |
| **Ticket** | `BOT-D04` (внутренний) |
| **Branch** | `feature/BAU/BOT-D04` |
| **Task spec** | [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md) |
| **Plan** | [tasks/D-04_DIALOG_HISTORY_YAML_plan.md](tasks/D-04_DIALOG_HISTORY_YAML_plan.md) |
| **Started** | 2026-04-15 |
| **Status** | Code complete, awaiting manual smoke-test in Telegram |
| **Owner** | Stan |

### Goal
Псевдо-память: хранить историю диалога per-user в YAML на диске, отправлять в LLM полную историю + новое сообщение, команда `/reset`.

### Success criteria

- [x] Unit тесты HistoryStore (8 шт) зелёные
- [x] Ruff lint чистый
- [x] `app/history/store.py` реализует YAML персистентность + sliding window + reset + corrupt recovery
- [x] Интеграция в `handle_message` — load history → build messages → LLM → append user+assistant
- [x] Команда `/reset` очищает историю
- [x] docker-compose volume `./data:/app/data` + container `user: 1000:1000` (permission fix)
- [ ] **Ручной smoke-test в Telegram** (ждёт пользователя):
  - [ ] Follow-up вопрос помнит контекст
  - [ ] `make restart` → история сохранилась
  - [ ] `/reset` → очищено, файл исчезает
  - [ ] Два аккаунта — изоляция
- [ ] Merge в master

### Pending action items

- [ ] **A1** · Ручной smoke-test из [plan.md Task 12](tasks/D-04_DIALOG_HISTORY_YAML_plan.md#task-12-финальный-прогон--manual-testing) · owner: Stan
- [ ] **A2** · Merge `feature/BAU/BOT-D04` → `master` после успешного smoke-теста · owner: Stan
- [ ] **A3** · Удалить `backup/d04-tangled` ветку после merge · owner: Stan
- [ ] **A4** · Добавить «Docker bind-mount UID mismatch» в legacy-warning / architecture edge cases (бонус, см. fix коммит `aae5549`) · owner: Stan/Claude

### Regression watch

- **Flow 2** (handle_message) изменён — risk: сломать single-message поведение. Тесты `test_llm_client` зелёные.
- **LLM context length** — длинные истории могут превысить context window. Window limit 20 смягчает.
- **`data/` volume** — добавлен в compose, требует UID match (fix `aae5549`). Если кто-то развернёт на machine с другим UID — `UID=XXXX GID=YYYY docker compose up` или в .env.
- **`_locks` dict** — утечка памяти мизерная (размер = число когда-либо активных юзеров), не проблема.

### Checkpoints

**Phase 0 (Design)** — 2026-04-15 — brainstorming завершён, variant B (persistent YAML), спек записан в [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md).

**Phase 1-4 (Code)** — 2026-04-15 — 11 чистых коммитов D-04 на feature branch (после разделения с C-01). 11/11 тестов зелёные, ruff чистый.

**Phase 5 (Infrastructure + bugfix)** — 2026-04-15 — докер deploy упал с `PermissionError` на `HistoryStore.mkdir()`. Root cause: bind-mount UID mismatch (host stan UID 1000, container botuser UID 999). Fix в коммите `aae5549` — `user: "${UID:-1000}:${GID:-1000}"` в compose. Бот запустился, уже обрабатывает сообщения от @StasMura (user_id 356640470).

**Phase 6 (Manual test)** — _ждёт пользователя_

**Phase 7 (Docs update)** — 2026-04-15 — все docs обновлены (commit `cbc1937`): architecture, context-dump Flow 2 + новый Flow 9, discuss § 2, legacy-warning § 4, db-schema, ui-kit, tech-stack, tasks, current-sprint.

### History

- 2026-04-15 09:XX — task started, brainstorming
- 2026-04-15 09:XX — spec + plan записаны
- 2026-04-15 09:XX — первая попытка implementation: 11 коммитов, часть оказалась tangled с pre-existing C-01 изменениями
- 2026-04-15 09:XX — rebuild: C-01 вынесен на master (`debb155`), feature branch пересобрана чисто
- 2026-04-15 09:XX — docs update (`cbc1937`)
- 2026-04-15 09:XX — deploy fail: PermissionError, fix `aae5549` (container user match)
- 2026-04-15 — awaiting smoke-test

---

## C-01 · Migrate LLM server from Ollama to Lemonade

| Поле | Значение |
|------|----------|
| **Task ID** | `C-01` |
| **Branch** | (merged на master напрямую) |
| **Status** | ✅ Merged 2026-04-15 · commit `debb155` |
| **Owner** | Stan |

### Goal
Перевести бот с Ollama на Lemonade (OpenAI-compatible) — переименование `ollama_base_url` → `llm_base_url`, смена endpoint `/api/tags` → `/v1/models`, docker-compose сервис, `.env.example`.

### Done
- [x] `app/config.py` — `llm_base_url`
- [x] `app/llm/client.py` — `/v1/models` с парсингом `data["data"][id]`
- [x] `app/main.py` — `llm_url` в лог-строке
- [x] `.env.example` — `LLM_BASE_URL=http://lemonade:8000/api`, `DEFAULT_MODEL=Qwen3-0.6B-GGUF`
- [x] `docker-compose.yml` — `lemonade` сервис (без ollama)
- [x] `tests/conftest.py` — `LLM_BASE_URL` env var
- [x] `lemonade/Dockerfile` — новый build context

### Remaining (out of C-01 scope, захватит C-02)
- [ ] `README.md` — всё ещё упоминает Ollama
- [ ] `Makefile` `pull-models` target — всё ещё вызывает `ollama pull`

См. [legacy-warning.md § 1](legacy-warning.md#1-ollama--lemonade-несогласованность) и [legacy-warning.md § 2](legacy-warning.md#2-makefile-pull-models-сломан).
