# Current Sprint — Sprint 2 (started 2026-04-23)

**Sprint 1 закрыт 2026-04-17.**

- Sprint 1 delivery: [sprint-1-delivery.md](sprint-1-delivery.md)
- Sprint 1 archive: [sprint-1-archive.md](sprint-1-archive.md)
- Скриншоты Sprint 1: [dialogs/](../dialogs/)
- Промты Sprint 1: [prompts-sprint-1.md](../prompts/prompts-sprint-1.md)

Итого в Sprint 1 закрыто: **9 задач** (C-01, C-02, D-04, D-05, D-06, D-07, D-08, D-09, D-10). 29/29 unit-тестов зелёные, ruff clean. Бот в проде на `master` с полным D-04..D-10 стеком. Push на GitHub — `Stanislav2014/ai-bot`.

---

## To Do

- **S-02** — Blue Team: закрыть 9 findings из S-01 (1 High, 4 Medium, 3 Low, 1 Info) · в работу пока не брать · inputs: [S-01](../tasks/S-01_RED_TEAM.md) + [results](../security/red-team-results.md)

## In Progress

_пусто_

## In Review

_пусто_

## Done (этот спринт)

- **C-04** — Modular monolith: Users / Chat / History boundaries · merged 2026-04-26 (no-ff) · 52/52 tests · [spec](../tasks/C-04_MODULAR_MONOLITH.md)
- **C-05** — In-memory event bus: decouple Chat ↔ History via events · merged 2026-04-26 (no-ff) · 69/69 tests · [spec](../tasks/C-05_EVENT_BUS.md)
- **S-01** — Red Team audit (Часть 1 ДЗ «Безопасность») · merged 2026-04-27 (no-ff) · 9 findings, 1 High · [spec](../tasks/S-01_RED_TEAM.md)
- **I-01** — CI/CD pipeline + LLM_ENABLED feature flag · merged 2026-04-27 (no-ff) · 72/72 tests · CI зелёный за 17s · [spec](../tasks/I-01_GITHUB_ACTIONS.md) · [PR #1](https://github.com/Stanislav2014/ai-bot/pull/1)
- **O-01** — Структурированный логгер с trace_id (Часть 1 ДЗ «Логирование + Sentry») · merged 2026-05-03 (no-ff) · 91/91 tests · ruff clean · CI зелёный за 19s · [spec](../tasks/O-01_LOGGING.md) · [PR #2](https://github.com/Stanislav2014/ai-bot/pull/2)
- **O-02** — Sentry: error tracking c корреляцией по `trace_id` (Часть 2 ДЗ «Логирование + Sentry») · merged 2026-05-03 (no-ff) · 102/102 tests · ruff clean · CI зелёный за 15s · [spec](../tasks/O-02_SENTRY.md) · [PR #3](https://github.com/Stanislav2014/ai-bot/pull/3)
- **O-02.1** — Hotfix PII утечек в Sentry (`system_prompt` через breadcrumb JSON message + `TELEGRAM_BOT_TOKEN` через httpx URLs) · merged 2026-05-03 (no-ff) · 110/110 tests · ruff clean · CI зелёный за 17s · [spec](../tasks/O-02.1_PII_HOTFIX.md) · [PR #4](https://github.com/Stanislav2014/ai-bot/pull/4)
- **O-02.2** — Hotfix третьего канала утечки токена (URL в plain-text `bc.message` от httpx-логгера) · merged 2026-05-03 (no-ff) · 114/114 tests · ruff clean · CI зелёный за 17s · [spec](../tasks/O-02.2_SCRUB_URL_IN_MESSAGE.md) · [PR #5](https://github.com/Stanislav2014/ai-bot/pull/5)

---

## Бэклог

Идеи для следующих спринтов вынесены в [backlog.md](backlog.md).

---

## Notes

- Рабочий процесс: [instructions.md](instructions.md) — TDD + branch prefixes + change-request как зеркало спринта (правка после feedback Stan 2026-04-15)
- Для новой задачи: скопировать блок шаблона из [change-request-doc.md](change-request-doc.md) в [change-request.md](change-request.md), добавить строку в [tasks.md](tasks.md), перенести в `To Do` / `In Progress` здесь
