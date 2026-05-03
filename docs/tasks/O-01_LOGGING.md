# O-01 · Структурированный логгер с trace_id

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `O-01` (новая фаза `O-` — Observability) |
| **Ticket** | — (homework: «Логирование + интеграция с Sentry», Часть 1) |
| **Branch** | `feature/OBS/O-01-logger` |
| **Started** | 2026-04-30 |
| **Status** | In Progress |
| **Owner** | Stan + Claude (autopilot) |

---

## Goal

Каждая строка лога приложения — JSON со стабильным набором полей: `timestamp`, `level`, `event`, `service`, `trace_id`. Все логи одного входящего апдейта связаны общим `trace_id` (uuid4). Логирование расставлено в 4 категориях: incoming events, business actions, errors, external services. Sentry — отдельной задачей O-02 (вне scope).

## Success criteria (verifiable)

- [ ] **CR-1**: JSON output содержит обязательные поля → verify: новый `tests/test_logging_config.py` парсит stdout `capsys`, проверяет наличие `timestamp`, `level`, `event`, `service`, `trace_id`
- [ ] **CR-2**: `service=ai-bot` в каждой строке → verify: тест на processor с фейковым event_dict
- [ ] **CR-3**: `trace_id` — валидный uuid4 hex (32 hex char), уникален на каждый update → verify: тест на middleware, прогоняет 2 update'а, ассертит разные trace_id
- [ ] **CR-4**: `trace_id` propagates в любой downstream-лог в рамках одного update (chat/llm/history/users) → verify: интеграционный тест через `ChatService.reply` с замоканным LLM, проверяет что `trace_id` из contextvars попадает в JSON всех логов
- [ ] **CR-5**: `user_id` в contextvars при наличии `from_user` → verify: тест middleware с message и с callback_query
- [ ] **CR-6**: contextvars очищаются между update'ами (нет leak'а) → verify: тест: bind+log+clear+log → второй лог без trace_id/user_id
- [ ] **CR-7**: внешние сервисы — лог при success и failure → verify: тесты `test_llm_client.py` уже покрывают `llm_request`/`llm_response`/error events; убедиться что `failed_to_list_models` теперь использует `logger.exception` (traceback в JSON)
- [ ] **CR-8**: `make test` зелёный, `make lint` clean
- [ ] **CR-9**: ручная проверка — `docker compose up`, отправить 3 сообщения боту, в `data/logs/bot.log` каждое — JSON с trace_id, в рамках одного запроса все логи (incoming → user_message → llm_request → llm_response → llm_reply) делят один trace_id

---

## Scope

### In scope
- Новое поле `service_name: str = "ai-bot"` в `app/config.py`
- Кастомный processor `_add_service` в `app/logging_config.py`
- Helper-модуль `app/observability.py` с функциями `new_trace_id()`, `bind_request_context()`, `clear_request_context()`
- Модификация `LoggingMiddleware` — на каждый Update генерит trace_id, биндит в contextvars + user_id
- Замена `logger.warning("failed_to_list_models")` → `logger.exception` в `LLMClient.list_models` (для tracebacks при сетевых сбоях)
- `tests/test_logging_config.py` — новый, тесты на JSON shape и processor
- `tests/test_middleware.py` — новый, тесты на trace_id middleware
- Дополнить `tests/test_chat_service.py` интеграционным тестом trace_id propagation
- Обновить `.env.example` с `SERVICE_NAME`

### Out of scope
- Sentry SDK интеграция → отдельная задача `O-02`
- Изменение существующих event-имён / breaking changes в формате
- Replacing `logger.error` на `logger.exception` для known LLM errors (LLMError имеет категории, traceback не нужен — это business errors не крэши)
- Добавление `request_id` отдельно от `trace_id` (1 trace_id = 1 update достаточно)
- OpenTelemetry / distributed tracing (single-process bot)

---

## Impact

### Новые файлы
| Файл | Назначение |
|------|------------|
| `app/observability.py` | helpers: `new_trace_id()`, `bind_request_context()`, `clear_request_context()` |
| `tests/test_logging_config.py` | проверка JSON-shape, service processor |
| `tests/test_middleware.py` | проверка trace_id binding, user_id binding, clear leak-safety |
| `docs/tasks/O-01_LOGGING.md` | этот файл |

### Изменяемые файлы
| Файл | Характер |
|------|----------|
| `app/config.py` | +`service_name: str = "ai-bot"` |
| `app/logging_config.py` | +processor `_add_service` (читает `settings.service_name`) |
| `app/bot/middleware.py` | `check_update` — clear contextvars, generate trace_id, bind trace_id + user_id + update_id |
| `app/llm/client.py` | `list_models()` — `logger.warning` → `logger.exception` для traceback |
| `tests/test_chat_service.py` | +1 тест на trace_id propagation |
| `.env.example` | +`SERVICE_NAME=ai-bot` |

---

## Design notes

**Почему contextvars, а не передача trace_id через kwargs:**
- structlog уже подключил `merge_contextvars` processor → contextvars автоматически инжектятся во все логи task'а
- PTB v21 запускает каждый update в отдельной asyncio Task → contextvars task-scoped, не текут между запросами
- Не надо менять сигнатуры всех existing methods (handlers, ChatService, LLMClient...)

**Почему trace_id, а не update_id:**
- `update_id` — Telegram's identifier, не uuid, человекочитаем но не уникален глобально (счётчик)
- `trace_id` (uuid4 hex) — стандарт для distributed tracing, легко гуглить в логах
- Оба биндим: `trace_id` для cross-system, `update_id` как отдельное поле для Telegram-debug

**Почему clear_contextvars() на входе middleware:**
- Belt-and-braces: даже если PTB поведение поменяется и task переиспользуется, контекст не утечёт
- Pure-overhead minimal — contextvars maps очень быстрые

---

## TDD phases

### Phase 0 — Research ✅
- [x] Прочитан `logging_config.py`, `middleware.py`, все handlers, `chat/service.py`, `llm/client.py`, `history/store.py`, `users/store.py`
- [x] Все вызывают `structlog.get_logger()` глобально → contextvars подхватятся автоматически
- [x] PTB v21+ обрабатывает каждый update в отдельной Task — contextvars изолированы

### Phase 1 — Logger core (service field)
- [ ] RED: тест что JSON содержит `service=ai-bot`
- [ ] GREEN: processor `_add_service` + поле в Settings
- [ ] REFACTOR

### Phase 2 — trace_id middleware
- [ ] RED: тест что middleware на каждый Update биндит uuid4 trace_id + user_id + update_id
- [ ] RED: тест что 2 разных update'а получают разные trace_id
- [ ] RED: тест что callback_query тоже даёт user_id
- [ ] GREEN: модификация `check_update`
- [ ] REFACTOR

### Phase 3 — Propagation integration test
- [ ] RED: интеграционный тест — bind trace_id вручную, прогон `ChatService.reply` с моками, capsys собирает JSON-stdout, ассертит trace_id в каждой строке (incoming → llm_request → llm_response → llm_reply)
- [ ] GREEN: должно работать «бесплатно» благодаря `merge_contextvars` (если нет — debug)

### Phase 4 — Coverage gaps
- [ ] `LLMClient.list_models` → `logger.exception` (traceback при сетевых сбоях)

### Phase 5 — Verify
- [ ] `make test` — все тесты зелёные (72 + ~6 новых)
- [ ] `make lint` — clean
- [ ] Manual: docker compose up + 3 сообщения, grep `bot.log` по trace_id, убедиться что все строки одного запроса связаны

### Phase 6 — Docs
- [ ] tasks.md → новая фаза `Phase O — Observability`, блок O-01 ✅
- [ ] current-sprint.md → перенос в Done
- [ ] change-request.md → блок O-01 со статусом Merged
- [ ] context-dump.md → обновить раздел про формат логов

---

## Regression watch

- **Tests с capsys**: `JSONRenderer` пишет одной строкой; парсить `json.loads` каждую строку. Не сломать существующие тесты которые могли бы парсить старый формат.
- **Contextvars в pytest**: каждый async test — отдельная Task, изоляция должна быть автоматической; но если тест биндит и не чистит — повлияет на следующие в том же event loop. Использовать pytest fixture с `autouse=True` который чистит до/после.
- **Middleware order**: `LoggingMiddleware` уже регистрируется `group=-1`, что гарантирует что он первым обрабатывает update. Не трогать порядок.

---

## History

- 2026-04-30 — спека + ветка
