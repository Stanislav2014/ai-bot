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
| **Status** | In Review (52/52 tests, ruff clean, awaiting manual Telegram smoke + merge) |
| **Owner** | Stan |

**Goal**: разнести бот на 4 изолированных модуля (`users/`, `chat/`, `history/`, `llm/`) + транспорт `bot/`. Handlers больше не импортят `LLMClient`/`HistoryStore` напрямую — только через `UserService` + `ChatService`.

**Success criteria**:
- [ ] CR-1 — `app/bot/handlers.py` без импортов `app.llm` / `app.history`
- [ ] CR-2/3 — модули `users/`, `history/`, `llm/` друг друга не знают
- [ ] CR-4 — выбор модели persistent (YAML per-user в `data/users/`), переживает рестарт; закрывает D-03
- [ ] CR-5 — все user-facing flow идентичны
- [ ] CR-6 — `make test` + `make lint` зелёные

См. [task spec](tasks/C-04_MODULAR_MONOLITH.md) для полной декомпозиции.

---

## C-05 · In-memory event bus — decouple Chat ↔ History via events

| Поле | Значение |
|------|----------|
| **Task ID** | `C-05` |
| **Branch** | `feature/TD/C-05-event-bus` |
| **Task spec** | [tasks/C-05_EVENT_BUS.md](tasks/C-05_EVENT_BUS.md) |
| **Started** | 2026-04-25 |
| **Status** | In Review (69/69 tests, ruff clean, DI smoke OK, awaiting manual Telegram smoke + merge) |
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
