# Архитектура

## Обзор

ai-bot — простой монопроцессный Python async-сервис. Одна точка входа, один event loop, без фоновых воркеров, без БД.

```
┌──────────┐   polling     ┌──────────────┐    HTTP     ┌──────────┐
│ Telegram │ ───────────▶  │  ai-bot      │ ──────────▶ │ Lemonade │
│   API    │ ◀───────────  │  (Python)    │ ◀────────── │  /v1/... │
└──────────┘  send reply   └──────────────┘   OpenAI    └──────────┘
                                                        compatible
```

---

## Паттерны

### 1. Stateless message processing

Каждое сообщение пользователя — изолированный LLM-запрос:
- без истории диалога
- без persistence message ID / counter / context
- system prompt жёстко зашит ([app/bot/handlers.py:10](../app/bot/handlers.py))

**Плюсы**: простота, отсутствие race conditions, отсутствие БД, детерминированные ошибки.
**Минусы**: нет follow-up вопросов, нет memory. Осознанный trade-off.

### 2. Per-user model selection (in-memory)

`BotHandlers.user_models: dict[int, str]` хранит выбранную модель per-user до рестарта процесса. После рестарта — все сбрасываются на `settings.default_model`.

**Почему не persistence**: для MVP достаточно; добавление персиста = или SQLite, или JSON файл, что ломает «stateless» принцип первого релиза.

### 3. OpenAI-compatible abstraction

Весь LLM взаимодействие через `/v1/chat/completions`. Это позволяет подставить **любой** OpenAI-compatible сервер (Ollama, Lemonade, vLLM, LM Studio) без изменений клиентского кода.

[app/llm/client.py](../app/llm/client.py) — единственный слой зависимый от HTTP API.

### 4. Graceful error handling пирамидой

```
LLMClient — поднимает LLMError с типизированным сообщением
     │
     ▼
BotHandlers.handle_message — ловит LLMError, преобразует в user-friendly текст
     │     (404 → спецобработка, остальное → generic)
     ▼
BotHandlers.handle_message — ловит Exception (BaseHandler catch-all)
```

Ни одна необработанная ошибка не доходит до пользователя — только «Sorry, try again».

### 5. Structured JSON logging

`structlog` с `JSONRenderer` → stdout. Каждый лог-event содержит `user_id`, `username`, `model` где уместно. Docker собирает stdout → `docker logs`.

[app/logging_config.py](../app/logging_config.py)

### 6. Shutdown через signal handlers

`SIGINT` / `SIGTERM` → `stop_event.set()` → корректный teardown `app.updater.stop()` → `app.stop()` → `llm.close()`. [app/main.py:40-61](../app/main.py).

---

## Компоненты (таблица)

| Компонент | Файл | Ответственность |
|-----------|------|----------------|
| Entry point | [app/main.py](../app/main.py) | Setup, регистрация хэндлеров, polling loop, graceful shutdown |
| Config | [app/config.py](../app/config.py) | Pydantic settings из `.env` |
| Logging setup | [app/logging_config.py](../app/logging_config.py) | structlog configure (JSON renderer) |
| LLM Client | [app/llm/client.py](../app/llm/client.py) | httpx async → OpenAI-compatible API |
| Bot Handlers | [app/bot/handlers.py](../app/bot/handlers.py) | Команды + текстовые сообщения + inline buttons |
| Logging middleware | [app/bot/middleware.py](../app/bot/middleware.py) | Логирование каждого входящего update (через check_update hack) |

---

## Edge cases

Собранные тонкие места. Если будешь менять связанный код — проверь что edge case не сломался.

### 1. `LoggingMiddleware.check_update()` возвращает `False`

[app/bot/middleware.py:29](../app/bot/middleware.py)

Не совсем middleware: это `BaseHandler` с `check_update → False`, чтобы update **не поглощался** и дошёл до следующего хэндлера. Hidden constraint: любой рефактор должен сохранять `return False`, иначе хэндлеры перестанут получать сообщения.

### 2. `LLMClient.list_models()` fallback на `AVAILABLE_MODELS`

[app/llm/client.py:60-70](../app/llm/client.py)

При любой ошибке (`except Exception`) возвращается хардкод список `["gpt-oss-20b", "qwen3:0.6b", "qwen3.5:27b"]`. Hidden constraint: этот список может **не совпадать** с реально установленными на Lemonade моделями. Пользователь может выбрать модель из fallback-списка, получить «Switched», а потом 404 при `chat()`. См. [legacy-warning.md § 3](legacy-warning.md#3-list_models-fallback-вводит-в-заблуждение).

### 3. Per-user state теряется при рестарте

[app/bot/handlers.py:16](../app/bot/handlers.py)

`self.user_models = {}` — dict в памяти экземпляра `BotHandlers`. Docker restart / deploy → все пользователи сбрасываются. Это **by design** для MVP, но пользователи могут не знать.

### 4. Stale inline keyboard после `/model <name>`

Если пользователь открыл `/models`, получил inline keyboard, потом в другом сообщении сделал `/model X` — inline клавиатура в старом сообщении остаётся со старым маркером `>`. Это косметика, не блокер.

### 5. `/v1/models` endpoint доступен не у всех LLM серверов

OpenAI-compatible серверы иногда возвращают `400` или `404` на `/v1/models`. Код это ловит (`except Exception`) и молча fallback-ит. См. edge case #2.

### 6. Signal handlers только на asyncio loop

[app/main.py:47-48](../app/main.py)

`loop.add_signal_handler` работает только на Unix. На Windows не заработает — но проект предназначен для Linux (Docker), так что это осознанное ограничение.

### 7. `list_models()` вызывается multiple times per user action

На `/models` → 1 вызов. На tap на inline button → ещё 1 вызов (для отрисовки обновлённой клавиатуры). На `/model <name>` → ещё 1 (валидация). При спам-нажатиях — много HTTP запросов к LLM серверу. См. [discuss.md § 6](discuss.md#6-model-list-caching).

### 8. `default_model` vs реальный merge порядок

`app/config.py` имеет `llm_base_url: str = "http://ollama:11434"` (hardcoded default). `.env.example` переопределяет на `http://lemonade:8000/api`. Если кто-то зальёт проект **без** `.env` — config подхватит Python default и попытается пойти на `ollama:11434`, а docker-compose запускает `lemonade`. Ошибка «Cannot connect». См. [legacy-warning.md § 1](legacy-warning.md#1-ollama--lemonade-несогласованность).

### 9. Startup race: polling начинается раньше чем Lemonade готов

`docker compose up` поднимает оба сервиса. `depends_on: lemonade` в docker-compose обеспечивает **старт**, но не **готовность**. Если бот начал polling, а Lemonade ещё грузит модель, первый `/message` вернёт ошибку. На практике первый cold start лечится повтором.

### 10. `httpx.AsyncClient` без явного connect pool limit

Pool default — хватает для одного бота. Если когда-нибудь появится parallel tasks — может потребоваться настроить `httpx.Limits`.
