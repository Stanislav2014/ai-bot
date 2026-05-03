# O-02 · Sentry — error tracking c trace_id корреляцией

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `O-02` (Phase O — Observability) |
| **Ticket** | — (homework: «Логирование + интеграция с Sentry», Часть 2) |
| **Branch** | `feature/OBS/O-02-sentry` |
| **Started** | 2026-05-03 |
| **Status** | Merged 2026-05-03 (no-ff) · [PR #3](https://github.com/Stanislav2014/ai-bot/pull/3) |
| **Owner** | Stan + Claude (autopilot) |

---

## Goal

Все необработанные исключения и `logger.error/exception` отправляются в Sentry с тэгами `trace_id`, `user_id`, `update_id` (из contextvars O-01) — чтобы конкретную ошибку можно было кликнуть и увидеть полную цепочку JSON-логов одного запроса. Конфиг через `SENTRY_DSN` env: пустая строка → SDK no-op (CI/dev безопасны). PII не утекает: `send_default_pii=False`, `before_send` чистит чувствительные поля.

## Success criteria (verifiable)

- [ ] **CR-1**: `SENTRY_DSN: str = ""` в `app/config.py` (default пусто); пустой DSN → `sentry_sdk.init()` no-op, бот стартует без ошибок → verify: `tests/test_sentry.py::test_init_noop_when_dsn_empty`
- [ ] **CR-2**: При не-пустом DSN — `sentry_sdk.init()` вызывается с `dsn`, `environment=settings.service_name`, `send_default_pii=False`, `before_send` callback, `integrations=[LoggingIntegration(event_level=ERROR)]` → verify: `tests/test_sentry.py::test_init_called_with_expected_kwargs`
- [ ] **CR-3**: `bind_request_context` дополнительно делает `sentry_sdk.set_tag("trace_id", ...)` + `set_tag("user_id", ...)` + `set_tag("update_id", ...)` → verify: `tests/test_observability.py::test_bind_sets_sentry_tags`
- [ ] **CR-4**: `clear_request_context` зовёт `sentry_sdk.get_isolation_scope().clear()` (или эквивалент) — между update'ами тэги не утекают → verify: `tests/test_observability.py::test_clear_resets_sentry_tags`
- [ ] **CR-5**: `before_send` хук исключает поле `system_prompt` из любого `extra` / `breadcrumbs` (закрывает S-01 F-06 для Sentry-канала) → verify: `tests/test_sentry.py::test_before_send_strips_system_prompt`
- [ ] **CR-6**: `setup_sentry()` вызывается в `app/main.py::run()` сразу после `setup_logging()` — до создания любого сервиса → verify: импорт-смок + ручной grep
- [ ] **CR-7**: `LoggingIntegration` ловит `logger.exception` из `LLMClient.list_models` (которое уже добавили в O-01) — то есть сетевой сбой к Lemonade автоматически попадает в Sentry без изменения кода клиента → verify: integration test с моком `sentry_sdk.capture_event`
- [ ] **CR-8**: `make test` зелёный (все existing 91 + ~6 новых), `make lint` clean
- [ ] **CR-9**: ручная проверка — выставить `SENTRY_DSN` от тестового проекта Sentry, отправить боту команду которая упадёт (например `LLM_BASE_URL=http://nope:9999/api`), убедиться: в Sentry dashboard появилось событие с тэгами `trace_id`/`user_id`/`update_id` совпадающими с локальным JSON-логом

---

## Scope

### In scope
- `sentry-sdk` в `requirements.txt` (закрепить версию)
- `app/config.py` — `sentry_dsn: str = ""`, `sentry_traces_sample_rate: float = 0.0` (тесты на трэйсинг performance — out of scope)
- Новый модуль `app/sentry_config.py` — функция `setup_sentry()`, `before_send()` хук
- `app/observability.py` — `bind_request_context` / `clear_request_context` ставят/чистят Sentry tags
- `app/main.py` — `setup_sentry()` после `setup_logging()`
- `tests/test_sentry.py` — init no-op, init с DSN, before_send PII фильтр, integration с logger.exception
- Дополнить `tests/test_observability.py` (если есть) или создать — Sentry tag binding
- `.env.example` — `SENTRY_DSN=`

### Out of scope
- Performance tracing (`traces_sample_rate > 0`) — для одного бота излишне, отдельная задача O-03 если понадобится
- Sentry release tracking (нет CD)
- Custom breadcrumb logic — `LoggingIntegration` достаточно для базового кейса
- Profiling
- Sentry alerts / dashboards — это конфигурация в UI Sentry, не в коде
- Source maps / sourcecontext (Python — текстовый код, default behavior достаточен)

---

## Impact

### Новые файлы
| Файл | Назначение |
|------|------------|
| `app/sentry_config.py` | `setup_sentry()`, `before_send()` |
| `tests/test_sentry.py` | init/no-op/PII фильтр |
| `docs/tasks/O-02_SENTRY.md` | этот файл |

### Изменяемые файлы
| Файл | Характер |
|------|----------|
| `requirements.txt` | +`sentry-sdk==X.Y.Z` (закрепим mainstream stable) |
| `app/config.py` | +`sentry_dsn: str = ""`, +`sentry_traces_sample_rate: float = 0.0` |
| `app/observability.py` | `bind_request_context` → `sentry_sdk.set_tag(...)`; `clear_request_context` → scope.clear() |
| `app/main.py` | +`from app.sentry_config import setup_sentry`; вызов после `setup_logging()` |
| `.env.example` | +`SENTRY_DSN=` + комментарий про no-op при пустом значении |
| `tests/test_observability.py` (создаём если нет) | +тесты на Sentry tag binding/clear |

---

## Design notes

**Почему `app/sentry_config.py`, а не внутри `app/observability.py`:**
- `observability.py` — лёгкие helpers, чистый от внешних SDK (только structlog/contextvars + теперь `sentry_sdk.set_tag`)
- `sentry_config.py` — мирror `logging_config.py`: один модуль = один setup. Параллельная архитектура. Легко удалить если откажемся.
- Альтернатива (запихнуть в `logging_config.py`) ломает SRP.

**Почему `LoggingIntegration` вместо ручного `capture_exception`:**
- Sentry SDK сам слушает `logging` ROOT logger (через `LoggingIntegration`); structlog → stdlib logger (мы уже это сконфигурировали в O-01) → integration ловит автоматически
- `event_level=ERROR` → только ERROR/CRITICAL уходят как events в Sentry; INFO/WARNING — как breadcrumbs (контекст)
- Не нужно патчить existing `logger.exception` calls

**Почему `send_default_pii=False`:**
- Sentry SDK по умолчанию шлёт user IP, request headers, cookies, etc. Мы — Telegram бот без HTTP сервера, но bind_request_context биндит `user_id` уже как explicit tag — это намеренный sanitised identifier, а не email/IP.
- `send_default_pii=False` — defense in depth.

**Почему `before_send` фильтрует `system_prompt`:**
- S-01 F-06 (Low): system_prompt попадает в startup лог. Если включить Sentry breadcrumbs с уровня INFO, breadcrumb от `starting_bot` попадёт в payload и system_prompt уедет в Sentry.
- Простой strip ключа `system_prompt` из `event.get("extra", {})` и `event.get("breadcrumbs", {}).get("values", [])` — чистит обе поверхности.
- Если в будущем добавим больше sensitive ключей — расширим список в одном месте.

**Почему `environment=settings.service_name`:**
- У нас один service в одном repo, но spirit Sentry — разделять prod/dev/staging. `service_name` — наиболее устойчивый идентификатор (один бот = одна service entry в Sentry). Если потребуется prod/dev split — введём `SENTRY_ENVIRONMENT` env позже.

**Почему `clear()` scope в `clear_request_context`:**
- Sentry SDK 2.x использует `Scope.get_isolation_scope()` per-coroutine (как и contextvars). PTB запускает каждый update в Task → isolation scope изолируется автоматически.
- Belt-and-braces: явная очистка — гарантия отсутствия leak'а если PTB поведение поменяется.

---

## TDD phases

### Phase 0 — Research ✅
- [x] Прочитан `app/observability.py`, `app/logging_config.py`, `app/main.py`, `app/bot/middleware.py`, `app/config.py`
- [x] structlog → stdlib logger handler чейн уже есть → `LoggingIntegration` подключится без изменения логирования
- [x] PTB v21+ обрабатывает каждый update в отдельной asyncio Task → Sentry isolation scope per-task

### Phase 1 — Config + sentry_config skeleton
- [ ] RED: `tests/test_sentry.py::test_init_noop_when_dsn_empty` — мокаем `sentry_sdk.init`, ассертим что не вызвалось
- [ ] RED: `tests/test_sentry.py::test_init_called_with_expected_kwargs` — ассертим kwargs (dsn, environment, send_default_pii=False, before_send, integrations)
- [ ] GREEN: `app/sentry_config.py::setup_sentry()` + поля в Settings
- [ ] REFACTOR

### Phase 2 — before_send PII фильтр
- [ ] RED: `tests/test_sentry.py::test_before_send_strips_system_prompt` — фейковый event с `extra.system_prompt` + breadcrumb `system_prompt` → возврат event без этих полей
- [ ] GREEN: `_before_send()` impl
- [ ] REFACTOR

### Phase 3 — Sentry tags в bind/clear
- [ ] RED: `tests/test_observability.py::test_bind_sets_sentry_tags` — мокаем `sentry_sdk.set_tag`, ассертим вызовы для trace_id/user_id/update_id
- [ ] RED: `test_clear_resets_sentry_tags` — после `clear_request_context` теги исчезают
- [ ] GREEN: модификация `bind_request_context` / `clear_request_context`
- [ ] REFACTOR

### Phase 4 — main.py wiring
- [ ] RED: smoke test что `app/main.py` импортирует `setup_sentry`
- [ ] GREEN: добавить вызов в `run()`

### Phase 5 — Integration through LoggingIntegration
- [ ] RED: `test_logger_exception_captured_by_sentry` — мокаем `sentry_sdk.capture_event` (или используем sentry's TestTransport), вызываем `logger.exception` через structlog → ассертим event capture
- [ ] GREEN: должно работать «бесплатно» благодаря `LoggingIntegration` (если не ловит — debug propagation structlog → stdlib root logger)

### Phase 6 — Verify
- [ ] `make test` — все 91 + ~6 новых зелёные
- [ ] `make lint` — clean
- [ ] Manual: тестовый Sentry проект → DSN → бросить ошибку → дашборд показывает event с тэгами

### Phase 7 — Docs
- [ ] tasks.md → блок O-02 ✅
- [ ] current-sprint.md → перенос в Done
- [ ] change-request.md → блок O-02 со статусом Merged
- [ ] context-dump.md → секция «Observability» — упомянуть Sentry канал и трэйс-корреляцию
- [ ] legacy-warning.md → если S-01 F-06 закрывается через Sentry-фильтр — пометить

---

## Regression watch

- **`sentry_sdk.init()` глобальное** — если тест случайно настроит реальный DSN, события полетят наружу. Использовать только мок DSN типа `https://test@example.com/0` или мокать `sentry_sdk.init` напрямую.
- **`LoggingIntegration` дублирует логи** — by default integration вешается на root logger. Наш logger уже structured. Убедиться что breadcrumbs не пишут JSON в JSON.
- **Тесты с contextvars + Sentry tags** — нужен `autouse` fixture, очищающий и contextvars, и Sentry isolation scope между тестами. Иначе тест-leak.
- **`pin sentry-sdk version`** — обновления могут сломать API (был breaking change в 2.x). Закрепить mainstream stable, обновлять осознанно.

---

## Open questions / уточнения после Phase 0

1. **Какую версию `sentry-sdk` пиннить?** — последняя 2.x (≥2.20). Если у Stan'а есть прод-эксп с другой — переписать.
2. **Нужен ли `SENTRY_ENVIRONMENT` отдельно от `service_name`?** — пока нет; service_name=ai-bot покрывает один service. Если в будущем будет dev/prod split — добавим.
3. **Сэмплинг errors?** — нет, все errors в Sentry. Performance trace = 0% (out of scope).

---

## History

- 2026-05-03 — спека + ветка
- 2026-05-03 — Phase 1 (init/no-op/kwargs) + Phase 2 (`before_send` PII strip) + Phase 3 (Sentry tags в bind/clear) + Phase 4 (main wiring) + Phase 5 (LoggingIntegration handler levels verified). 102/102 tests, ruff clean. PR #3 merged в master (commit `6410bf8`).
- 2026-05-03 — Manual CR-9 (Sentry dashboard verification) — outstanding на стороне Stan'а.
