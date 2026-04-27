# Change Request — Sprint 2 (started 2026-04-23)

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
| **Status** | In Review (72/72 tests локально, ждёт первого зелёного run на GitHub Actions + merge) |
| **Owner** | Stan |

**Goal**: автоматическая проверка любых изменений (lint + test) до merge. Pipeline быстрый, изолированный, без сети к Telegram/Lemonade. Бонус — feature flag `LLM_ENABLED` для maintenance/cost-control.

**Success criteria**:
- [x] CR-1..CR-5 — workflow создан, триггерится на push/PR, кэширует pip, запускает ruff + pytest, env vars изолируют от сети
- [x] CR-6 — никаких реальных секретов в коде (`.env` в `.gitignore`)
- [x] CR-7 (бонус) — feature flag `LLM_ENABLED` реализован (3 теста)
- [x] CR-8 — 72/72 tests green локально
- [ ] CR-9 — первый run на GitHub Actions зелёный (verify после push)

См. [task spec](tasks/I-01_GITHUB_ACTIONS.md) для полной декомпозиции.
