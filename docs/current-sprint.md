# Current Sprint

_Итерация: Sprint 1 — старт 2026-04-15_

Kanban для текущей активной работы. Master-каталог — в [tasks.md](tasks.md).

## To Do

_пусто_

## In Progress

_пусто_

## In Review

_пусто (D-04 ожидает ручного smoke-теста в Telegram)_

## Done (этот спринт)

### C-01 · Migrate LLM server from Ollama to Lemonade
Pre-existing uncommitted работа, сведена в отдельный коммит на master как часть чистки перед D-04. `llm_base_url`, docker-compose lemonade service, `/v1/models` в client, `lemonade/Dockerfile`.
- Commit: `debb155` (master)
- Closed: 2026-04-15

### D-04 · Dialog history — persistent YAML per-user
Псевдо-память: `data/history/{user_id}.yaml`, sliding window, `/reset`. 11 коммитов на ветке `feature/BAU/BOT-D04`, 11/11 тестов зелёные, lint чистый. Ожидает manual smoke-test и merge.
- Branch: `feature/BAU/BOT-D04`
- Spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)
- Completed (code): 2026-04-15

---

## Notes

- Sprint 1 — первый спринт после развёртывания doc-структуры
- D-04 требует ручной smoke-тест в реальном Telegram до merge в master (см. [tasks/D-04_DIALOG_HISTORY_YAML_plan.md Task 12](tasks/D-04_DIALOG_HISTORY_YAML_plan.md))
- Остаток C-01: README.md упоминания Ollama, Makefile `pull-models` — вынести в отдельный C-02 коммит
- Backup branch `backup/d04-tangled` можно удалить после успешного merge D-04 в master
