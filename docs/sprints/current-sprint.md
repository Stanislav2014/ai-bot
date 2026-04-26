# Current Sprint — Sprint 2 (started 2026-04-23)

**Sprint 1 закрыт 2026-04-17.**

- Sprint 1 delivery: [sprint-1-delivery.md](sprint-1-delivery.md)
- Sprint 1 archive: [sprint-1-archive.md](sprint-1-archive.md)
- Скриншоты Sprint 1: [dialogs/](../dialogs/)
- Промты Sprint 1: [prompts-sprint-1.md](../prompts/prompts-sprint-1.md)

Итого в Sprint 1 закрыто: **9 задач** (C-01, C-02, D-04, D-05, D-06, D-07, D-08, D-09, D-10). 29/29 unit-тестов зелёные, ruff clean. Бот в проде на `master` с полным D-04..D-10 стеком. Push на GitHub — `Stanislav2014/ai-bot`.

---

## To Do

_пусто_

## In Progress

_пусто_

## In Review

- **C-04** — Modular monolith: Users / Chat / History boundaries · [spec](../tasks/C-04_MODULAR_MONOLITH.md) · ветка `feature/TD/C-04-modular-monolith` · 52/52 tests, ruff clean, ждёт ручной Telegram-smoke + merge
- **C-05** — In-memory event bus: decouple Chat ↔ History via events · [spec](../tasks/C-05_EVENT_BUS.md) · ветка `feature/TD/C-05-event-bus` (поверх C-04) · 69/69 tests, ruff clean, DI smoke OK, ждёт ручной Telegram-smoke + merge

## Done (этот спринт)

_пусто_

---

## Бэклог

Идеи для следующих спринтов вынесены в [backlog.md](backlog.md).

---

## Notes

- Рабочий процесс: [instructions.md](instructions.md) — TDD + branch prefixes + change-request как зеркало спринта (правка после feedback Stan 2026-04-15)
- Для новой задачи: скопировать блок шаблона из [change-request-doc.md](change-request-doc.md) в [change-request.md](change-request.md), добавить строку в [tasks.md](tasks.md), перенести в `To Do` / `In Progress` здесь
