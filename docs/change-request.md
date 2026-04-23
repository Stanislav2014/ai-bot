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
