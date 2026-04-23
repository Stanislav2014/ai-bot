# Backlog

Идеи для будущих спринтов. Источники: [ideas.md](../ideas.md), [discuss.md](../discuss.md), [legacy-warning.md](../legacy-warning.md).

При старте нового спринта — выбрать задачи отсюда, перенести в [current-sprint.md](current-sprint.md) → `To Do`, добавить блок в [change-request.md](../change-request.md).

---

- **C-03** — TTL-кеш для `list_models()` (избыточные HTTP на каждое переключение модели)
- **D-03** — persistent `user_models` dict (сейчас in-memory, теряется при рестарте)
- Улучшение UX: команда `/stats` / `/history` — показать размер текущего контекста
- Streaming ответы (сейчас blocking)
- Rate-limiting / allowlist (если понадобится публичное развёртывание)
- Актуализация `README.md` — дополнительный cleanup после C-01 (ссылки на Ollama убраны, но можно ещё пройтись)
