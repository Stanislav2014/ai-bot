# O-03 · Часть 3 ДЗ — четыре типа ошибок для verify Sentry + sentry_sdk.set_user

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `O-03` (Phase O — Observability) |
| **Ticket** | — (homework: «Логирование + Sentry», Часть 3) |
| **Branch** | `feature/OBS/O-03-error-scenarios` |
| **Started** | 2026-05-03 |
| **Status** | Merged 2026-05-03 (no-ff) · [PR #6](https://github.com/Stanislav2014/ai-bot/pull/6) |
| **Owner** | Stan + Claude (autopilot) |

---

## Goal

Закрыть Часть 3 ДЗ — искусственно сгенерировать 4 типа ошибок и убедиться что **каждая** отображается в Sentry с stack trace + контекстом + trace_id. На текущий момент покрыт только сценарий «ошибка внешнего взаимодействия» (Lemonade down → llm_connection_error). Остальные 3 — manual / async / data-format — не покрыты.

Бонус: `sentry_sdk.set_user({"id": ..., "username": ...})` в `bind_request_context` для лучшей идентификации в Sentry UI (User panel + filter by user.id).

## Success criteria (verifiable)

- [ ] **CR-1**: Команда `/sentry_test <kind>` где kind ∈ {`raise`, `async`, `external`, `data`} спровоцирует соответствующий тип ошибки → каждый kind покрыт unit-тестом на handler logic
- [ ] **CR-2**: Команда доступна **только** в whitelist `user_id` (Stan = 356640470), для всех остальных — сообщение «not allowed» (защита от случайной spam-обработки в Sentry)
- [ ] **CR-3**: `bind_request_context` дополнительно вызывает `sentry_sdk.set_user({"id": user_id, "username": ...})` если username/id заданы → unit test на mock `sentry_sdk.set_user`
- [ ] **CR-4**: `clear_request_context` сбрасывает user через `set_user(None)` или scope clear (которое уже делает clear) → verify
- [ ] **CR-5**: `make test` зелёный (114 + новые), `make lint` clean
- [ ] **CR-6**: Manual verify в Sentry для каждого из 4 типов:
  - **manual** (`/sentry_test raise`) — `RuntimeError("manual test")` → event с stack trace, `trace_id`, `user_id` tags
  - **async** (`/sentry_test async`) — `asyncio.create_task(...)` где coroutine raises → event с async stack trace
  - **external** (`/sentry_test external`) — попытка httpx GET к нерабочему URL `http://localhost:1/` → connection error event
  - **data** (`/sentry_test data`) — `json.loads("{not_valid")` → JSONDecodeError event
  Для каждого: `trace_id` совпадает с локальным JSON-логом, контекст (user_id) виден в Sentry tags, stack trace полный.

---

## Scope

### In scope
- `app/config.py` — `sentry_test_user_ids: list[int] = [356640470]` (whitelist через env, default = твой ID)
- `app/bot/handlers.py` — новый метод `sentry_test(self, update, context)` с диспатчем на 4 kind'а
- `app/main.py` — `CommandHandler("sentry_test", handlers.sentry_test)`
- `app/observability.py` — `bind_request_context` дополнительно `sentry_sdk.set_user({...})`; добавить `username` в args
- `app/bot/middleware.py` — пробрасывать `username` в `bind_request_context`
- `tests/test_handlers.py` (новый) — unit-тесты на 4 kind'а + whitelist guard
- `tests/test_observability.py` — расширить тестами на set_user

### Out of scope
- Real-time alerts / Slack integration в Sentry
- Custom Sentry release tags / source map upload
- E-mail/контакты пользователя — у нас и нет такой инфы (Telegram даёт только id/username)
- Обработка raised ошибок специальным way — пускай PTB error handler стандартно их ловит и Sentry собирает

---

## Design notes

**Почему whitelist `user_id`:**
- `/sentry_test` — это **демонстрационная** команда, она засоряет Sentry events. Если кто-то узнает имя команды — может заDoS'ить наш Sentry quota.
- Whitelist прост и эффективен. Stan единственный (пока) пользователь.
- Не использую `is_admin` от Telegram chat — это бот, не группа.

**Почему 4 разных триггера а не один общий:**
- ДЗ требует **отдельных** сценариев — Sentry должен отличать manual error от data error от async (по типу exception, по stack trace).
- Каждый тип демонстрирует разный path к Sentry: sync raise → PTB error handler → Sentry · async create_task → asyncio default exception handler → Sentry · httpx error → exception в handler → Sentry · json.JSONDecodeError → exception в handler → Sentry.

**`sentry_sdk.set_user` — единый вызов:**
- Sentry's User context отдельный от tags: даёт UI panel «User» в event view + фильтр в Discover.
- `clear_request_context` уже делает `get_isolation_scope().clear()` — это полностью сбрасывает scope, включая user. Дополнительный `set_user(None)` не нужен.

**Async error через asyncio.create_task:**
- В PTB v21 async error handlers ловят исключения из основного flow (`handle_message` etc.). Но `asyncio.create_task(...)` создаёт fire-and-forget task — её исключения **не** доходят до PTB error handler.
- Эти fire-and-forget исключения попадают в `loop.default_exception_handler` → stdlib `logging.error` → `LoggingIntegration` → Sentry.
- Это легитимный сценарий ДЗ.

---

## TDD phases

### Phase 1 — set_user в bind/clear (RED→GREEN)
- RED: `test_bind_calls_sentry_set_user_when_user_id_present`
- RED: `test_bind_skips_set_user_when_user_id_none`
- GREEN: расширить `bind_request_context` + сигнатуру (добавить `username: str | None = None`)
- Обновить middleware вызовы

### Phase 2 — `/sentry_test` handler
- RED: `test_sentry_test_rejects_non_whitelisted_user`
- RED: `test_sentry_test_raise_kind_raises_runtime_error`
- RED: `test_sentry_test_data_kind_raises_json_decode_error`
- RED: `test_sentry_test_async_kind_creates_task_with_error`
- RED: `test_sentry_test_external_kind_raises_httpx_error`
- GREEN: implement handler
- Wire up в main.py

### Phase 3 — Verify
- `make test` все зелёные, `make lint` clean

### Phase 4 — Manual verify (CR-6)
- Запускаем 4 сценария по очереди → проверяем Sentry events для каждого

### Phase 5 — Docs
- mark Done в tasks.md, current-sprint.md, change-request.md
- закрывает Часть 3 ДЗ полностью

---

## Regression watch

- `set_user` принимает dict; при NoneType `id`/`username` — пропускать (не вызывать или вызывать с пустым dict).
- `/sentry_test` НЕ должен висеть в `BotCommands` Telegram menu (чтобы не виден чужим). PTB CommandHandler ловит только если пользователь явно ввёл — этого достаточно.
- В whitelist test'ах НЕ хардкодить user_id 356640470 в коде — должна быть из settings. Тест монkeypatch'ит settings.

---

## History

- 2026-05-03 — спека + ветка
