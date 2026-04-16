# Change Request — Sprint 1 (2026-04-15)

> 📋 Зеркало текущего спринта: каждая задача, которая находится в [current-sprint.md](current-sprint.md), имеет блок здесь. При merge задачи запись **не удаляется** — обновляется статус. Чистится только при закрытии спринта (архивации в task spec history).

---

## D-07 · System prompt — configurable persona

| Поле | Значение |
|------|----------|
| **Task ID** | `D-07` |
| **Ticket** | `BOT-D07` |
| **Branch** | `feature/BAU/BOT-D07` (от master после merge D-04/D-05/D-06) |
| **Task spec** | [tasks/D-07_SYSTEM_PROMPT.md](tasks/D-07_SYSTEM_PROMPT.md) |
| **Started** | 2026-04-15 |
| **Status** | In Progress — Phase 0 (paperwork done, implementation ahead) |
| **Owner** | Stan |

### Goal
Сделать system prompt configurable через env `SYSTEM_PROMPT` с осмысленным дефолтом (русский программистский persona). Инъекция в `BotHandlers.__init__` вместо module-level константы.

### Success criteria

- [ ] `settings.system_prompt` (env `SYSTEM_PROMPT`) работает, дефолт — русский программист
- [ ] `BotHandlers.__init__` принимает `system_prompt`, использует `self.system_prompt` в `handle_message`
- [ ] Module-level `SYSTEM_PROMPT` удалена
- [ ] main.py wiring + truncated log field
- [ ] `.env.example` обновлён с русским примером
- [ ] 24 существующих теста зелёные, ruff чистый
- [ ] Ручной smoke: программистский тон в ответах + override через env меняет стиль
- [ ] Merge в master

### Pending action items

- [ ] **A1** · Phase 1: config + .env.example
- [ ] **A2** · Phase 2: handlers refactor (инъекция, замена константы)
- [ ] **A3** · Phase 3: main.py wiring
- [ ] **A4** · Phase 4: lint + tests
- [ ] **A5** · Phase 5: manual smoke-test (owner: Stan)
- [ ] **A6** · Phase 6: docs update
- [ ] **A7** · Merge D-07 → master

### Regression watch

- `handle_message` единственная точка использования — низкий risk
- Существующие 24 теста не трогают handlers directly → должны остаться зелёными
- `Summarizer` изолирован, его `SUMMARY_PROMPT` отдельная сущность

### Checkpoints

**Phase 0** — 2026-04-15 — brainstorming, вариант A утверждён (env-configurable, русский дефолт, no per-user override), spec записан, ветка создана

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

## D-05 · Context char limit — второй safeguard

| Поле | Значение |
|------|----------|
| **Task ID** | `D-05` |
| **Ticket** | `BOT-D05` |
| **Branch** | `feature/BAU/BOT-D05` (dependent от `feature/BAU/BOT-D04`) |
| **Task spec** | [tasks/D-05_CONTEXT_CHAR_LIMIT.md](tasks/D-05_CONTEXT_CHAR_LIMIT.md) |
| **Plan** | [tasks/D-05_CONTEXT_CHAR_LIMIT_plan.md](tasks/D-05_CONTEXT_CHAR_LIMIT_plan.md) |
| **Started** | 2026-04-15 |
| **Status** | Code complete, awaiting manual smoke-test and merge (depends on D-04 merge first) |
| **Owner** | Stan |

### Goal
Кап по суммарной длине истории диалога (`HISTORY_MAX_CHARS`, default 8000 chars). Работает поверх D-04 count-limit как AND-safeguard: если одна длинная простыня раздувает историю выше бюджета — FIFO-обрезка до `≤ max_chars`. Последнее (только что пришедшее) сообщение защищено от drop.

### Success criteria

- [x] 4 новых unit теста зелёные (`test_char_limit_*`)
- [x] 8 существующих history тестов не сломаны
- [x] `make test` (15 тестов: 3 LLM + 12 history) зелёный
- [x] `make lint` чистый
- [x] `HISTORY_MAX_CHARS` env var работает (default 8000, 0 = disabled)
- [x] main.py передаёт max_chars в HistoryStore, в `starting_bot` логе видно поле
- [ ] Ручной тест: 3 длинных (~3000 chars) сообщения подряд → 4-е получает историю ≤8000 chars
- [ ] Merge в master (после merge D-04)

### Pending action items

- [x] **A1** · Task 1: `max_chars` kwarg default=0 (backwards compat) · commit `aa3d832`
- [x] **A2** · Task 2: TDD char-trim logic · commit `65de5da`
- [x] **A3** · Task 3: edge cases (disabled, single-oversize, combined) · commit `2d80141`
- [x] **A4** · Task 4-5: config + main.py wiring · commits `47aa2d5`, `eca354c`
- [x] **A5** · Task 6: docs update (architecture, context-dump Flow 2, tech-stack)
- [ ] **A6** · Task 7: manual verification в Telegram с длинными сообщениями (owner: Stan)
- [ ] **A7** · Merge D-05 → master (после D-04 merge)

### Regression watch

- HistoryStore API расширен новым kwarg — защита через default=0 backwards compat
- Существующие 8 history тестов — gate на регрессию
- Flow 2 в handlers.py не меняется (HistoryStore инкапсулирует логику)

### Checkpoints

**Phase 0** — 2026-04-15 — спек + plan записаны, paperwork обновлён, ветка `feature/BAU/BOT-D05` создана от HEAD D-04

**Phase 1-3 (TDD HistoryStore)** — 2026-04-15 — 9→12 тестов history_store, backwards compat подтверждена, 4 новых char-limit теста зелёные. Коммиты `aa3d832`, `65de5da`, `2d80141`.

**Phase 4-5 (Config + wiring)** — 2026-04-15 — `history_max_chars=8000` в settings, .env.example, main.py wiring. `starting_bot` лог содержит `history_max_chars`. Коммиты `47aa2d5`, `eca354c`.

**Phase 6 (Docs)** — 2026-04-15 — architecture § 1 (D-04/D-05 pattern расширен), context-dump Flow 2 (шаги 14-15 упоминают двухступенчатый trim), tech-stack env table, tasks.md ✅, current-sprint.md → In Review.

---

## D-06 · History summarization — умная обрезка через LLM

| Поле | Значение |
|------|----------|
| **Task ID** | `D-06` |
| **Ticket** | `BOT-D06` |
| **Branch** | `feature/BAU/BOT-D06` (dependent от `feature/BAU/BOT-D05`) |
| **Task spec** | [tasks/D-06_HISTORY_SUMMARIZATION.md](tasks/D-06_HISTORY_SUMMARIZATION.md) |
| **Plan** | [tasks/D-06_HISTORY_SUMMARIZATION_plan.md](tasks/D-06_HISTORY_SUMMARIZATION_plan.md) |
| **Started** | 2026-04-15 |
| **Status** | Code complete, awaiting manual smoke-test and merge (depends on D-04/D-05 merge first) |
| **Owner** | Stan |

### Goal
Умная обрезка истории: при `len > HISTORY_SUMMARIZE_THRESHOLD` (default 5) старые сообщения заменяются single summary-system-message через отдельный LLM-запрос, последние `HISTORY_KEEP_RECENT` (default 2) сохраняются raw. Fail-safe: ошибка LLM не блокирует основной ответ.

### Success criteria

- [x] `app/history/summarizer.py` с `Summarizer` + `maybe_summarize`
- [x] `HistoryStore.replace(user_id, new_history)` новый метод
- [x] `tests/test_summarizer.py` — 8 тестов зелёные
- [x] `tests/test_history_store.py` — +1 тест на `replace` зелёный
- [x] `make test` всего 24 теста зелёные
- [x] `make lint` чистый
- [x] `HISTORY_SUMMARIZE_THRESHOLD=0` → точное D-05 поведение (gate на regression, покрыт тестом)
- [x] main.py wiring; `starting_bot` лог включает summarize-поля
- [ ] Ручной smoke: 6+ сообщений → появляется `role: system` summary в `data/history/<user_id>.yaml`, лог `history_summarized`
- [ ] Merge в master (после D-04, D-05)

### Pending action items

- [x] **A1** · Task 1: `HistoryStore.replace` TDD · commit `88400d0`
- [x] **A2** · Task 2: Summarizer skeleton + below-threshold tests · commit `608cc34`
- [x] **A3** · Task 3: happy path RED→GREEN · commit `c5fa605`
- [x] **A4** · Task 4: behavior tests (role, keep_recent, payload, failure, empty) · commit `b12edcc`
- [x] **A5** · Task 5: config + .env.example · commit `77d7a18`
- [x] **A6** · Task 6: BotHandlers + main.py wiring · commit `8cdf7a2`
- [x] **A7** · Task 7: docs update
- [ ] **A8** · Task 8: manual smoke-test (owner: Stan)
- [ ] **A9** · Merge D-06 → master (после merge D-04 и D-05)

### Regression watch

- `HISTORY_SUMMARIZE_THRESHOLD=0` gate — все 15 существующих тестов должны оставаться зелёными
- Failure в summary LLM call → fall-through, основной ответ пользователю не блокируется
- Handler flow меняется (summarizer call между get и build payload) — тестов handlers нет, ручная проверка
- Extra latency на триггер (+1 LLM call) — документируется, приемлемо для локальной модели

### Checkpoints

**Phase 0** — 2026-04-15 — brainstorming done, spec + plan записаны, ветка `feature/BAU/BOT-D06` создана от HEAD D-05 (commit `48392f7`)

**Phase 1 (HistoryStore.replace TDD)** — 2026-04-15 — RED → GREEN → 13/13 history tests green. Commit `88400d0`.

**Phase 2-3 (Summarizer skeleton + happy path)** — 2026-04-15 — skeleton с below-threshold guard + happy path с LLM mock. Commits `608cc34`, `c5fa605`.

**Phase 4 (Behavior tests)** — 2026-04-15 — role system check, keep_recent intact, payload transcript format, LLM failure fallback, empty response fallback. Commit `b12edcc`. 8/8 summarizer tests green.

**Phase 5 (Config + wiring)** — 2026-04-15 — 3 новых env, handle_message вызывает summarizer + replace + лог `history_summarized`, main.py резолвит `summarize_model`. 24/24 tests green, ruff clean. Commits `77d7a18`, `8cdf7a2`.

**Phase 6 (Docs)** — 2026-04-15 — architecture § 1 расширена D-06 bullet-ом + edge cases 15-16 (recursive merge, latency), context-dump Flow 2 step 6.5, tech-stack 3 env строки, tasks.md ✅, current-sprint.md → In Review.

**Phase 7 (Manual smoke-test)** — _ждёт пользователя_

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
