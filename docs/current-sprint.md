# Current Sprint

_Итерация: Sprint 1 — старт 2026-04-15_

Kanban для текущей активной работы. Master-каталог — в [tasks.md](tasks.md).

## To Do

_пусто_

## In Progress

### D-04 · Dialog history — persistent YAML per-user
Псевдо-память: `data/history/{user_id}.yaml`, full history → LLM, `/reset` command, window через `HISTORY_MAX_MESSAGES`.
- Branch: `feature/BAU/BOT-D04`
- Started: 2026-04-15
- Spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)
- Change request: [change-request.md](change-request.md)
- Phase: 0 (Research / Design)

## In Review

_пусто_

## Done (этот спринт)

_пусто_

---

## Notes

- Sprint 1 — первый спринт после развёртывания doc-структуры (2026-04-15)
- D-04 меняет stateless-архитектуру: теперь бот персистит историю диалога на диск
- После D-04 обновить: `discuss.md § 2`, `legacy-warning.md § 4` (per-user state in memory), `context-dump.md Flow 2`, `db-schema.md`, `architecture.md`
