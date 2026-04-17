# Current Sprint

_Итерация: Sprint 1 — старт 2026-04-15_

Kanban для текущей активной работы. Master-каталог — в [tasks.md](tasks.md).

## To Do

_пусто_

## In Progress

_пусто_

## In Review

_пусто_

## Done (этот спринт)

### D-10 · HISTORY_ENABLED flag — выключаемый контекст
Env `HISTORY_ENABLED=false` делает `HistoryStore.get/append/replace` no-op — бот становится полностью stateless. Merged 2026-04-17, 29/29 тесты зелёные.
- Spec: [tasks/D-10_HISTORY_ENABLED_FLAG.md](tasks/D-10_HISTORY_ENABLED_FLAG.md)

### D-09 · Dual logging — stdout + rotating file в проекте
structlog → stdlib → 2 handler-а (StreamHandler + RotatingFileHandler 10MB × 5). Файл `data/logs/bot.log` доступен на хосте без sudo, переживает recreate. Merged 2026-04-17.
- Spec: [tasks/D-09_LOG_FILE_ROTATION.md](tasks/D-09_LOG_FILE_ROTATION.md)

### D-08 · Context logging — visibility перед LLM call
`llm_request` лог с `total_chars`, `estimated_tokens`, full `messages` (под env gate `LOG_CONTEXT_FULL`). Helper `_context_stats` + 3 unit теста. Merged 2026-04-15.
- Spec: [tasks/D-08_CONTEXT_LOGGING.md](tasks/D-08_CONTEXT_LOGGING.md)

### D-07 · System prompt — configurable persona
Env `SYSTEM_PROMPT` (default: русский программист). Инъекция в `BotHandlers`, module-level константа удалена. Merged 2026-04-15.
- Spec: [tasks/D-07_SYSTEM_PROMPT.md](tasks/D-07_SYSTEM_PROMPT.md)

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
- Все 5 запланированных задач (D-04..D-08) + бонус (C-01) закрыты кодом и merged в master. Deliverable: [sprint-1-delivery.md](sprint-1-delivery.md).
- Pending (не блокирует sprint-close):
  - Ручной smoke-test в реальном Telegram (owner: Stan)
  - `git push origin master` (блокирован GitHub-требованием verify email)
  - C-02: починить `Makefile pull-models` под Lemonade
  - Backup branch `backup/d04-tangled` можно удалить
