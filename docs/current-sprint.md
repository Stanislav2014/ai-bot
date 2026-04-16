# Current Sprint

_Итерация: Sprint 1 — старт 2026-04-15_

Kanban для текущей активной работы. Master-каталог — в [tasks.md](tasks.md).

## To Do

_пусто_

## In Progress

### D-07 · System prompt — configurable persona
Env `SYSTEM_PROMPT` вместо hardcoded константы. Дефолт — русский программистский persona. Инъекция в `BotHandlers.__init__`.
- Branch: `feature/BAU/BOT-D07` (от master после D-04/D-05/D-06 merge)
- Started: 2026-04-15
- Spec: [tasks/D-07_SYSTEM_PROMPT.md](tasks/D-07_SYSTEM_PROMPT.md)
- Phase: 0 (paperwork done, implementation ahead)

## In Review

_пусто_

## Done (этот спринт)

### C-01 · Migrate LLM server from Ollama to Lemonade
Pre-existing uncommitted работа, сведена в отдельный коммит на master как часть чистки перед D-04. `llm_base_url`, docker-compose lemonade service, `/v1/models` в client, `lemonade/Dockerfile`.
- Commit: `debb155` (master)
- Closed: 2026-04-15

### D-04 · Dialog history — persistent YAML per-user
Псевдо-память: `data/history/{user_id}.yaml`, sliding window, `/reset`. Merged 2026-04-15.
- Spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)

### D-05 · Context char limit — второй safeguard
`HISTORY_MAX_CHARS` default 8000, FIFO-обрезка поверх count-trim. Last-message protected. Merged 2026-04-15.
- Spec: [tasks/D-05_CONTEXT_CHAR_LIMIT.md](tasks/D-05_CONTEXT_CHAR_LIMIT.md)

### D-06 · History summarization — умная обрезка через LLM
Summarizer класс + `HistoryStore.replace`. При `len > 5` старые сообщения заменяются single summary-system-message через LLM-запрос, последние 2 сохраняются raw. Fail-safe. Merged 2026-04-15.
- Spec: [tasks/D-06_HISTORY_SUMMARIZATION.md](tasks/D-06_HISTORY_SUMMARIZATION.md)

---

## Notes

- Sprint 1 — первый спринт после развёртывания doc-структуры
- D-04/D-05/D-06 смержены в master 2026-04-15. Ручной smoke-тест пока откладывается.
- Остаток C-01: README.md упоминания Ollama, Makefile `pull-models` — вынести в отдельный C-02 коммит
- Backup branch `backup/d04-tangled` можно удалить в любой момент (feature ветки уже merged и удалены)
