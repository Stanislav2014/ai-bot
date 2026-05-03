# Change Request — Sprint 2 (started 2026-04-23, текущий день 2026-04-30)

> 📋 Зеркало текущего спринта: каждая задача, которая находится в [current-sprint.md](sprints/current-sprint.md), имеет блок здесь. При merge задачи запись **не удаляется** — обновляется статус. Чистится только при закрытии спринта (архивации в task spec history).

**Sprint 1 закрыт 2026-04-17.** Архив прошлого спринта — [sprint-1-archive.md](sprints/sprint-1-archive.md). Финальный delivery-документ — [sprint-1-delivery.md](sprints/sprint-1-delivery.md).

---

## C-04 · Modular monolith — Users / Chat / History boundaries

| Поле | Значение |
|------|----------|
| **Task ID** | `C-04` |
| **Branch** | `feature/TD/C-04-modular-monolith` |
| **Task spec** | [tasks/C-04_MODULAR_MONOLITH.md](tasks/C-04_MODULAR_MONOLITH.md) |
| **Started** | 2026-04-23 |
| **Status** | Merged 2026-04-26 (no-ff) · 52/52 tests · ruff clean |
| **Owner** | Stan |

**Goal**: разнести бот на 4 изолированных модуля (`users/`, `chat/`, `history/`, `llm/`) + транспорт `bot/`. Handlers больше не импортят `LLMClient`/`HistoryStore` напрямую — только через `UserService` + `ChatService`.

**Success criteria**:
- [x] CR-1 — `app/bot/handlers.py` без импортов `app.llm` / `app.history`
- [x] CR-2/3 — модули `users/`, `history/`, `llm/` друг друга не знают
- [x] CR-4 — выбор модели persistent (YAML per-user в `data/users/`), переживает рестарт; закрывает D-03
- [x] CR-5 — все user-facing flow идентичны
- [x] CR-6 — `make test` + `make lint` зелёные

См. [task spec](tasks/C-04_MODULAR_MONOLITH.md) для полной декомпозиции.

---

## C-05 · In-memory event bus — decouple Chat ↔ History via events

| Поле | Значение |
|------|----------|
| **Task ID** | `C-05` |
| **Branch** | `feature/TD/C-05-event-bus` |
| **Task spec** | [tasks/C-05_EVENT_BUS.md](tasks/C-05_EVENT_BUS.md) |
| **Started** | 2026-04-25 |
| **Status** | Merged 2026-04-26 (no-ff) · 69/69 tests · ruff clean · DI smoke OK |
| **Owner** | Stan |

**Goal**: внедрить простой in-memory event bus и развязать `chat/` от `history/`. Chat публикует `MessageReceived` / `ResponseGenerated` / `HistorySummarized` / `HistoryResetRequested`, History подписывается. Бонус: `UserCreated` для будущих обработчиков.

**Решение по ходу**: добавлено 5-е событие `HistoryResetRequested` (изначально планировалось 4). Иначе `chat.reset_history` оставался прямым вызовом `history.reset` — нарушение «Chat не вызывает History напрямую». Sequential publish гарантирует, что к моменту возврата история сброшена → семантика для пользователя идентична.

**Success criteria**:
- [x] CR-1 — `app/chat/` без импорта `app.history` → grep clean
- [x] CR-2 — `app/history/` не импортит `chat/users/bot/llm` → grep clean
- [x] CR-3 — `app/events/` — zero app-deps → grep clean
- [x] CR-4 — `ChatService.reply` публикует `MessageReceived` + `ResponseGenerated`; summarize → `HistorySummarized`; reset → `HistoryResetRequested`. Verified в `test_chat_service.py` (11 тестов, включая failure path)
- [x] CR-5 — `UserService.get_or_create` публикует `UserCreated` только для нового. Verified в `test_user_service.py` (3 новых теста)
- [x] CR-6 — History subscriber: 4 события → правильные методы store. Verified в `test_history_subscriber.py` (6 тестов, включая per-user isolation)
- [x] CR-7 — User-facing flow идентичен (логи `llm_reply` / `history_summarized` те же; порядок записи в историю сохранён через sequential publish). DI smoke без сети подтверждает что события прокидываются и история реально пишется.
- [x] CR-8 — `make test` 69/69 ✅, `make lint` clean ✅

См. [task spec](tasks/C-05_EVENT_BUS.md) для полной декомпозиции.

---

## S-01 · Red Team audit — взлом своего бота

| Поле | Значение |
|------|----------|
| **Task ID** | `S-01` (новая фаза `S-` — Security) |
| **Branch** | `feature/SEC/S-01-red-team` |
| **Task spec** | [tasks/S-01_RED_TEAM.md](tasks/S-01_RED_TEAM.md) |
| **Started** | 2026-04-27 |
| **Status** | Merged 2026-04-27 (no-ff) · без правок кода — только аудит-документ + сырые результаты |
| **Owner** | Stan + Claude (autopilot) |

**Goal**: прогнать стандартный набор Red Team атак (prompt injection, data leakage, jailbreak, API/backend, tool abuse) и задокументировать findings с severity для входа в S-02 Blue Team.

**Method**: 5 источников без правки кода — direct Lemonade с тем же system_prompt, static analysis `app/bot/handlers.py`, YAML-store fuzz, multi-turn `ChatService.reply` симуляция, forensic над `data/`.

**Findings (9):**
- F-01 **High** · persistent injection через summarizer → инъекция попадает в system-message навсегда
- F-02 Medium · `model_callback` не валидирует `model_name` (defense-in-depth дыра)
- F-03 Medium · `/model` skip валидации когда `installed=[]` (Lemonade down → poison)
- F-04 Medium · 0.6B сдаётся на persona override (DAN)
- F-05 Medium · 0.6B hallucinates env/files/logs — мисинформация
- F-06 Low · system_prompt в startup-логе
- F-07 Low · format hijack (JSON output)
- F-08 Low · нет rate-limit (известно)
- F-09 Info · нет input length cap до LLM

**Артефакты**:
- [docs/tasks/S-01_RED_TEAM.md](tasks/S-01_RED_TEAM.md) — полный анализ + recommendations
- [docs/security/red-team-results.md](security/red-team-results.md) — сырые ответы Lemonade на 17 payload'ов × 2 модели

**Telegram-side тесты (M-01..M-05)** — переданы Stan для ручного прогона (rate-limit, длинные сообщения, /reset behaviour).

---

## S-02 · Blue Team — закрыть findings из S-01

| Поле | Значение |
|------|----------|
| **Task ID** | `S-02` |
| **Branch** | TBD (`feature/SEC/S-02-blue-team`) |
| **Task spec** | TBD (создаётся при подъёме в In Progress) |
| **Status** | To Do (в работу пока не брать) |
| **Owner** | Stan |

**Goal**: реализовать защиты для всех findings из S-01 (Часть 2 ДЗ «Безопасность» — Blue Team).

**Scope (предварительно):**
- F-01 High · summarizer-injection: stricter system-prompt для summarizer, или обернуть summary в `<summary>` теги с pre-instruction «не trust'ать», или вообще structured output вместо free text
- F-02 Medium · добавить валидацию `model_name not in installed` в `model_callback` (3 строки кода)
- F-03 Medium · отказ менять модель когда `list_models()` пустой + whitelist regex для имени
- F-04 + F-05 Medium · усилить system-prompt anti-jailbreak инструкциями + (опционально) сменить default модель на 4B
- F-06 Low · убрать `system_prompt` из startup-лога или хешировать
- F-07 Low · output format guard
- F-08 Low · rate-limit (per-user token bucket в bot/middleware)
- F-09 Info · cap на длину одного сообщения до отправки в LLM

См. [S-01 spec](tasks/S-01_RED_TEAM.md) для полного контекста и [raw results](security/red-team-results.md).

---

## I-01 · CI/CD pipeline через GitHub Actions

| Поле | Значение |
|------|----------|
| **Task ID** | `I-01` (новая фаза `I-` — Infrastructure / DevOps) |
| **Branch** | `feature/CI/I-01-github-actions` |
| **Task spec** | [tasks/I-01_GITHUB_ACTIONS.md](tasks/I-01_GITHUB_ACTIONS.md) |
| **Started** | 2026-04-27 |
| **Status** | Merged 2026-04-27 (no-ff) · CI зелёный за 17s ([PR #1](https://github.com/Stanislav2014/ai-bot/pull/1)) · 72/72 tests · ruff clean |
| **Owner** | Stan |

**Goal**: автоматическая проверка любых изменений (lint + test) до merge. Pipeline быстрый, изолированный, без сети к Telegram/Lemonade. Бонус — feature flag `LLM_ENABLED` для maintenance/cost-control.

**Success criteria**:
- [x] CR-1..CR-5 — workflow создан, триггерится на push/PR, кэширует pip, запускает ruff + pytest, env vars изолируют от сети
- [x] CR-6 — никаких реальных секретов в коде (`.env` в `.gitignore`)
- [x] CR-7 (бонус) — feature flag `LLM_ENABLED` реализован (3 теста)
- [x] CR-8 — 72/72 tests green локально
- [x] CR-9 — первый run на GitHub Actions зелёный (PR #1, 17s, все 8 шагов success)

См. [task spec](tasks/I-01_GITHUB_ACTIONS.md) для полной декомпозиции.

---

## O-02.2 · Hotfix — третий канал утечки токена в Sentry (URL в plain-text message)

| Поле | Значение |
|------|----------|
| **Task ID** | `O-02.2` (hotfix к O-02.1) |
| **Branch** | `feature/OBS/O-02.2-scrub-url-in-message` |
| **Task spec** | [tasks/O-02.2_SCRUB_URL_IN_MESSAGE.md](tasks/O-02.2_SCRUB_URL_IN_MESSAGE.md) |
| **Started** | 2026-05-03 |
| **Status** | In Progress |
| **Owner** | Stan + Claude (autopilot) |

**Goal**: при re-verify O-02.1 обнаружено что **дефолтный httpx-логгер** пишет URL в plain-text `bc["message"]` (`HTTP Request: POST https://api.telegram.org/bot<TOKEN>/getMe ...`), а O-02.1 чистил только `bc["data"]["url"]` и JSON-в-message. Это **третий канал утечки** токена.

**Solution**:
- `_scrub_breadcrumb_message` теперь **всегда** применяет `_scrub_url` к строке (regex), независимо от формата (JSON или plain text). JSON-парсинг остаётся для удаления sensitive ключей (system_prompt).
- `_before_breadcrumb` дополнительно вызывает `_scrub_breadcrumb_message` — первая линия защиты до попадания breadcrumb'а в scope.
- `_before_send` чистит `event["logentry"]["message"]` (defense in depth для error events с logentry payload).

**Tests**: 110 → 114 (+4). См. [task spec](tasks/O-02.2_SCRUB_URL_IN_MESSAGE.md).

**CR-6 (manual re-verify)**: после rebuild → провокация ошибки → ВСЕ httpx URLs в Sentry breadcrumbs (включая category=`httpx`) показывают `bot[REDACTED]/`.

---

## O-02.1 · Hotfix — закрыть утечки PII в Sentry

| Поле | Значение |
|------|----------|
| **Task ID** | `O-02.1` (hotfix к O-02) |
| **Branch** | `feature/OBS/O-02.1-pii-hotfix` |
| **Task spec** | [tasks/O-02.1_PII_HOTFIX.md](tasks/O-02.1_PII_HOTFIX.md) |
| **Started** | 2026-05-03 |
| **Status** | Merged 2026-05-03 (no-ff) · 110/110 tests · ruff clean · CI зелёный за 17s · [PR #4](https://github.com/Stanislav2014/ai-bot/pull/4) |
| **Owner** | Stan + Claude (autopilot) |

**Goal**: закрыть две PII утечки в Sentry, обнаруженные при manual CR-9 проверке O-02:
- **`system_prompt`** утекал через breadcrumb message: structlog `JSONRenderer` рендерит весь dict в `bc["message"]` JSON-строкой, мой `_before_send` чистил только `bc["data"]` (тест в O-02 покрывал design assumption, не реальный flow)
- **`TELEGRAM_BOT_TOKEN`** утекал в URL: дефолтная `HttpxIntegration` Sentry SDK логирует URL каждого httpx-запроса, Telegram кладёт токен в path → утечка на каждый `getUpdates`

**Solution**:
- `_before_send` парсит `bc["message"]` как JSON, чистит sensitive ключи, re-сериализует
- Новый `_before_breadcrumb` маскирует Telegram токен в `bc["data"]["url"]` через regex `_TG_TOKEN_RE` → `bot[REDACTED]/`
- Defense-in-depth: тот же scrub в `_before_send` для `event["request"]["url"]` и `bc["data"]["url"]`

**Tests**: 102 → 110 (+8). См. [task spec](tasks/O-02.1_PII_HOTFIX.md) для CR-1..CR-8.

**CR-8 (manual re-verify)**: ПОСЛЕ revoke токена + новый Sentry проект → спровоцировать ошибку → проверить отсутствие `system_prompt` и `bot[REDACTED]` вместо токена.

---

## O-02 · Sentry — error tracking c trace_id корреляцией

| Поле | Значение |
|------|----------|
| **Task ID** | `O-02` |
| **Branch** | `feature/OBS/O-02-sentry` |
| **Task spec** | [tasks/O-02_SENTRY.md](tasks/O-02_SENTRY.md) |
| **Started** | 2026-05-03 |
| **Status** | Merged 2026-05-03 (no-ff) · 102/102 tests · ruff clean · CI зелёный за 15s · [PR #3](https://github.com/Stanislav2014/ai-bot/pull/3) |
| **Owner** | Stan + Claude (autopilot) |

**Goal**: Часть 2 ДЗ «Логирование + Sentry». Все необработанные исключения и `logger.error/exception` уезжают в Sentry с тэгами `trace_id`/`user_id`/`update_id` (из contextvars O-01) — клик по error в Sentry даёт прямую связь с цепочкой JSON-логов одного запроса. Конфиг через `SENTRY_DSN`: пустая строка → SDK no-op (CI/dev безопасны). PII не утекает: `send_default_pii=False`, `before_send` чистит `system_prompt` (заодно закрывает S-01 F-06 для Sentry-канала).

**Success criteria**: см. [task spec](tasks/O-02_SENTRY.md) — 9 CR, ключевые: пустой DSN no-op, `bind_request_context` ставит Sentry tags, `LoggingIntegration` ловит `logger.exception` автоматически, `before_send` strip-ает sensitive поля.

**Architecture decisions**:
- Новый модуль `app/sentry_config.py` (мирror `logging_config.py`) — SRP
- `LoggingIntegration(event_level=ERROR)` — ловит structlog → stdlib root → Sentry без правки existing `logger.exception` calls
- Sentry tags — bind/clear в `app/observability.py` рядом с contextvars, единая точка trace context

См. [task spec](tasks/O-02_SENTRY.md) для полной декомпозиции.

---

## O-01 · Структурированный логгер с trace_id

| Поле | Значение |
|------|----------|
| **Task ID** | `O-01` (новая фаза `O-` — Observability) |
| **Branch** | `feature/OBS/O-01-logger` |
| **Task spec** | [tasks/O-01_LOGGING.md](tasks/O-01_LOGGING.md) |
| **Started** | 2026-04-30 |
| **Status** | Merged 2026-05-03 (no-ff) · 91/91 tests · ruff clean · CI зелёный за 19s · [PR #2](https://github.com/Stanislav2014/ai-bot/pull/2) |
| **Owner** | Stan + Claude (autopilot) |

**Goal**: Часть 1 ДЗ «Логирование + Sentry». JSON-логи со стабильным набором обязательных полей: `timestamp`, `level`, `event`, `service`, `trace_id`. Все логи одного входящего апдейта связаны общим `trace_id` (uuid4) через `structlog.contextvars`. Sentry — отдельная задача `O-02`.

**Success criteria**:
- [x] CR-1..CR-2 — JSON-shape (`service=ai-bot` в каждой строке) · `tests/test_logging_config.py` 8 тестов
- [x] CR-3..CR-4 — `trace_id` валидный uuid4 hex, propagates во все downstream-логи в рамках одного update · `tests/test_middleware.py::test_check_update_binds_uuid_trace_id` + `tests/test_chat_service.py::test_trace_id_propagates_into_chat_logs`
- [x] CR-5..CR-6 — `user_id` биндится при наличии `from_user` (message + callback_query), contextvars очищаются между update'ами
- [x] CR-7 — внешние сервисы: `LLMClient.list_models` → `logger.exception` для traceback (+ `format_exc_info` processor чтобы JSON содержал `exception` поле)
- [x] CR-8 — `make test` 91/91 ✅ · `make lint` clean ✅
- [x] CR-9 — smoke test (`/tmp/o01-smoke.log`) подтвердил: 4 лога одного запроса делят trace_id, второй update получает свежий uuid, все обязательные поля присутствуют

См. [task spec](tasks/O-01_LOGGING.md) для полной декомпозиции.
