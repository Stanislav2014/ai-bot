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

### C-02 ✅ Обновить Makefile pull-models под Lemonade
`pull-models` теперь `docker compose exec lemonade lemonade-server-dev pull Qwen3-0.6B-GGUF` + новый таргет `list-models` для просмотра доступных и установленных моделей.
Branch: `feature/TD/BOT-C02` · merged 2026-04-16
См. [legacy-warning.md § 2](legacy-warning.md#2-makefile-pull-models-сломан)

### C-03 📝 Кеш `list_models()`
HTTP запрос к LLM серверу на каждый `/models` и переключение. Добавить TTL-кеш на 60s.
См. [discuss.md § 6](discuss.md#6-model-list-caching)

### C-04 ✅ Modular monolith — Users / Chat / History boundaries
Разнести бот на 4 изолированных модуля (`users/`, `chat/`, `history/`, `llm/`) + транспорт `bot/`. Handlers больше не импортят `LLMClient`/`HistoryStore` напрямую. Закрывает D-03 (persistent per-user model selection).
Branch: `feature/TD/C-04-modular-monolith` · merged 2026-04-26 · 52/52 tests
→ [tasks/C-04_MODULAR_MONOLITH.md](tasks/C-04_MODULAR_MONOLITH.md)

### C-05 ✅ In-memory event bus — decouple Chat ↔ History via events
Внедрить `app/events/` (EventBus + 5 frozen-dataclass событий: `UserCreated`, `MessageReceived`, `ResponseGenerated`, `HistorySummarized`, `HistoryResetRequested`). Chat больше не вызывает `history.append/replace/reset` напрямую — публикует события, History подписывается через `app/history/subscriber.py`. `chat/` не импортит `app.history` (через `HistoryReader` Protocol). Часть 2 ДЗ «Эволюция архитектуры».
Branch: `feature/TD/C-05-event-bus` · merged 2026-04-26 · 69/69 tests
→ [tasks/C-05_EVENT_BUS.md](tasks/C-05_EVENT_BUS.md)

---

## Phase S — Безопасность

### S-01 ✅ Red Team audit — взлом своего бота
Часть 1 ДЗ «Безопасность». Прогнан без правок кода: 17 payload'ов × 2 модели через direct Lemonade, static analysis handlers, YAML-fuzz, multi-turn ChatService, log-forensic. **9 findings, 1 High** (persistent injection через summarizer попадает в system-message навсегда). 0.6B (default) сдалась на 7/17 атак, 4B (Stan's) — на 1/17. Артефакт для S-02 Blue Team.
Branch: `feature/SEC/S-01-red-team` · merged 2026-04-27
→ [tasks/S-01_RED_TEAM.md](tasks/S-01_RED_TEAM.md) · [results](security/red-team-results.md)

### S-02 📝 Blue Team — закрыть findings из S-01
Закрыть 9 уязвимостей найденных в S-01: persistent injection через summarizer (F-01 High), отсутствующая валидация в `model_callback` (F-02), bypass `/model` при `installed=[]` (F-03), persona override (F-04) и hallucinations (F-05) на 0.6B, system_prompt в логах (F-06), format hijack (F-07), rate-limit (F-08), input length cap (F-09). Часть 2 ДЗ «Безопасность» (Blue Team). **В работу пока не брать** — спека создаётся при подъёме в In Progress.
Inputs: [S-01 task spec](tasks/S-01_RED_TEAM.md), [raw results](security/red-team-results.md)

---

## Phase I — Infrastructure / DevOps

### I-01 🛠 CI/CD pipeline (GitHub Actions)
ДЗ «CI/CD для AI Telegram-бота». `.github/workflows/ci.yml` запускает lint (ruff) + test (pytest, 72 теста) на push/PR в master. Python 3.12, кэш pip по `requirements-dev.txt`. Тесты изолированы — мокают LLM (AsyncMock), не лезут в Telegram. **Бонус**: feature flag `LLM_ENABLED` — когда `false`, `ChatService.reply` возвращает canned reply без вызова LLM и без событий.
Branch: `feature/CI/I-01-github-actions`
→ [tasks/I-01_GITHUB_ACTIONS.md](tasks/I-01_GITHUB_ACTIONS.md)

---

## Phase D — Фичи

### D-01 ✅ Inline keyboard model selection
→ Commit f5de296 · 2026-04-10

### D-02 ✅ Лог переключения модели в чат
`previous → new` отдельным сообщением.
→ Commits 609e241, b0b0dd0 · 2026-04-10

### D-03 ✅ Persistent per-user model selection
Закрыта в рамках **C-04** (modular monolith): `app/users/store.py` хранит per-user state в YAML `data/users/{telegram_id}.yaml`. См. [discuss.md § 1](discuss.md#1-persistence-для-per-user-selected-model).

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
Branch: `feature/BAU/BOT-D07` · merged 2026-04-15 · 24/24 tests green
→ [tasks/D-07_SYSTEM_PROMPT.md](tasks/D-07_SYSTEM_PROMPT.md)

### D-08 ✅ Context logging — visibility перед LLM call
Расширяет event `llm_request` полями `total_chars`, `estimated_tokens` (`chars // 4` heuristic) и полным `messages` payload под гейтом env `LOG_CONTEXT_FULL` (default `true`). Покрывает оба LLM-вызова: основной диалог + summarization.
Branch: `feature/BAU/BOT-D08` · merged 2026-04-15 · 27/27 tests green
→ [tasks/D-08_CONTEXT_LOGGING.md](tasks/D-08_CONTEXT_LOGGING.md)

### D-09 ✅ Dual logging — stdout + rotating file в проекте
structlog форвардит в stdlib logging с двумя handler-ами: `StreamHandler(stdout)` (Docker compatible) + `RotatingFileHandler(data/logs/bot.log, 10MB × 5)`. Env `LOG_FILE` управляет путём.
Branch: `feature/BAU/BOT-D09` · merged 2026-04-17 · 27/27 tests green
→ [tasks/D-09_LOG_FILE_ROTATION.md](tasks/D-09_LOG_FILE_ROTATION.md)

### D-10 ✅ HISTORY_ENABLED flag — выключаемый контекст
Новый env `HISTORY_ENABLED` (default `true`). Когда `false` — `HistoryStore.get/append/replace` no-op, бот stateless. Исправляет неверный совет «поставь три лимита в 0» (давал противоположный эффект).
Branch: `feature/BAU/BOT-D10` · merged 2026-04-17 · 29/29 tests green
→ [tasks/D-10_HISTORY_ENABLED_FLAG.md](tasks/D-10_HISTORY_ENABLED_FLAG.md)
