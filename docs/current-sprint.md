# Current Sprint

**Sprint 1 закрыт 2026-04-17.**

- Delivery: [sprint-1-delivery.md](sprint-1-delivery.md)
- Archive (полный live change-request): [sprint-1-archive.md](sprint-1-archive.md)
- Скриншоты из Telegram: [dialogs/](dialogs/)
- Все промты спринта: [prompts-sprint-1.md](prompts-sprint-1.md)

Итого в Sprint 1 закрыто: **9 задач** (C-01, C-02, D-04, D-05, D-06, D-07, D-08, D-09, D-10). 29/29 unit-тестов зелёные, ruff clean. Бот в проде на `master` с полным D-04..D-10 стеком. Push на GitHub — `Stanislav2014/ai-bot`.

---

## To Do

_Sprint 2 не начат — новых задач нет._

## In Progress

_пусто_

## In Review

_пусто_

## Done (этот спринт)

_пусто (при старте Sprint 2)_

---

## Следующий спринт — идеи (backlog)

Из [ideas.md](ideas.md) / [discuss.md](discuss.md) / [legacy-warning.md](legacy-warning.md):

- **C-03** — TTL-кеш для `list_models()` (избыточные HTTP на каждое переключение модели)
- **D-03** — persistent `user_models` dict (сейчас in-memory, теряется при рестарте)
- Улучшение UX: команда `/stats` / `/history` — показать размер текущего контекста
- Streaming ответы (сейчас blocking)
- Rate-limiting / allowlist (если понадобится публичное развёртывание)
- Актуализация `README.md` — дополнительный cleanup после C-01 (ссылки на Ollama убраны, но можно ещё пройтись)

---

## Notes

- Рабочий процесс: [instructions.md](instructions.md) — TDD + branch prefixes + change-request как зеркало спринта (правка после feedback Stan 2026-04-15)
- Для новой задачи: скопировать блок шаблона из [change-request-doc.md](change-request-doc.md) в [change-request.md](change-request.md), добавить строку в [tasks.md](tasks.md), перенести в `To Do` / `In Progress` здесь
