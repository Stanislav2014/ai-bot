# Context Dump — карта взаимодействий

Технический атлас: как именно компоненты взаимодействуют. Все ссылки в формате `file:line`.

**Когда обновлять**: см. [instructions.md § 6 Post-merge](instructions.md#3-жизненный-цикл-задачи) — изменения Flow, внешних зависимостей, карты модулей или счётчика тестов.

---

## Flow 1 — Startup

**Trigger**: `python -m app.main` (или `docker compose up`)

1. `main()` → `asyncio.run(run())` · [app/main.py](../app/main.py)
2. `setup_logging()` → structlog configure JSON renderer · [app/logging_config.py](../app/logging_config.py)
3. `settings` инстанцируется из `.env` (pydantic-settings) · [app/config.py](../app/config.py)
4. DI-цепочка собирается в `main.run()`:
   - `EventBus()` — in-memory bus, sequential publish (C-05) · [app/events/bus.py](../app/events/bus.py)
   - `LLMClient()` — httpx AsyncClient с timeout · [app/llm/client.py](../app/llm/client.py)
   - `HistoryStore(history_dir, ...)` → `subscribe_history(bus, history)` подключает обработчики 4 событий (MessageReceived, ResponseGenerated, HistorySummarized, HistoryResetRequested) · [app/history/store.py](../app/history/store.py) · [app/history/subscriber.py](../app/history/subscriber.py)
   - `Summarizer(llm, threshold, keep_recent, model)` · [app/chat/summarizer.py](../app/chat/summarizer.py)
   - `UserStore(users_dir)` → `UserService(store, default_model=settings.default_model, bus=bus)` (публикует UserCreated при первом get_or_create) · [app/users/](../app/users/)
   - `ChatService(users, history, summarizer, llm, bus, system_prompt)` — `history` принимается как `HistoryReader` Protocol (только `.get`) · [app/chat/service.py](../app/chat/service.py)
   - `BotHandlers(users=users, chat=chat)` — транспорт зависит **только** от UserService и ChatService · [app/bot/handlers.py](../app/bot/handlers.py)
5. `ApplicationBuilder().token(...).build()` — python-telegram-bot Application
6. Регистрация handlers:
   - `LoggingMiddleware` (group=-1, всегда первый)
   - `CommandHandler("start" | "help" | "models" | "model" | "reset")`
   - `CallbackQueryHandler(pattern=r"^model:")` для inline buttons
   - `MessageHandler(filters.TEXT & ~filters.COMMAND)` — catch-all текст
7. Signal handlers: `SIGINT`, `SIGTERM` → `stop_event.set()`
8. `async with app: app.start() → app.updater.start_polling() → stop_event.wait()`
9. При сигнале: `updater.stop() → app.stop() → llm.close()`

---

## Flow 2 — Incoming text message (happy path)

**Trigger**: пользователь пишет текст боту в Telegram.

**Слои**: `bot/handlers.py` (транспорт) → `chat/service.py::ChatService.reply` (оркестрация) → `users` + `history` + `chat/summarizer` + `llm`.

1. `Update` приходит через polling в `Application` dispatcher
2. **LoggingMiddleware.check_update()** логирует `incoming_message` (user_id, username, chat_id, text[:200], message_id), возвращает `False` (не поглощает update) · [app/bot/middleware.py](../app/bot/middleware.py)
3. `MessageHandler(TEXT & ~COMMAND)` → `BotHandlers.handle_message` · [app/bot/handlers.py](../app/bot/handlers.py)
4. **Транспорт**: `model = await self.users.get_model(user_id)` для логирования; лог `user_message` (user_id, username, model, text_length); `chat.send_action("typing")`
5. **`reply = await self.chat.reply(user_id, text)`** — оркестрация (после C-05 — без прямых вызовов в history, всё через EventBus):
   1. `model = await users.get_model(telegram_id)` — fallback на `settings.default_model`, если у пользователя нет записи · [app/users/service.py](../app/users/service.py)
   2. `history_msgs = await history.get(telegram_id)` — единственный read-call в history (через Protocol `HistoryReader`); возвращает копию из cache → YAML · [app/history/store.py](../app/history/store.py)
   3. `new_history = await summarizer.maybe_summarize(history_msgs)` (D-06) — если `len > HISTORY_SUMMARIZE_THRESHOLD`, старые уходят в LLM на summary. При изменении — `await bus.publish(HistorySummarized(...))` (C-05) → подписчик `app/history/subscriber.py` зовёт `store.replace`. Лог `history_summarized` (before/after). Fail/disabled → возвращается без изменений · [app/chat/summarizer.py](../app/chat/summarizer.py)
   4. `messages = [{system: system_prompt}] + history_msgs + [{user: text}]` — system_prompt inject-ится в `ChatService.__init__` из `settings.system_prompt` (env `SYSTEM_PROMPT`, D-07)
   5. `result = await llm.chat(messages, model=model)` → HTTP POST `{base_url}/v1/chat/completions`, body `{model, messages, stream: false}` · [app/llm/client.py](../app/llm/client.py)
   6. Логи `llm_request` (model, messages_count, `total_chars`, `estimated_tokens`; + `messages` при `LOG_CONTEXT_FULL=true`, D-08) и `llm_response` (model, tokens) — внутри `LLMClient`
   7. `await bus.publish(MessageReceived(telegram_id, text))` (C-05) — запись user-message **после** успешного LLM-ответа. Подписчик зовёт `store.append("user", ...)` с count- + char-trim
   8. `await bus.publish(ResponseGenerated(telegram_id, reply))` — подписчик зовёт `store.append("assistant", ...)`
   9. Лог `llm_reply` (user_id, model, reply_length, history_len)
   10. Возврат `reply` транспорту
6. `update.message.reply_text(reply)` → отправка обратно в Telegram

**Важно**: bus.publish последовательный (sequential await subscribers). К моменту возврата `chat.reply` события уже обработаны и история записана на диск.

---

## Flow 3 — Incoming text message (error paths)

**Trigger**: та же точка входа, но LLM сервер отвечает ошибкой.

- `httpx.TimeoutException` → `LLMError("timed out after Ns")` · [app/llm/client.py:47-49](../app/llm/client.py)
- `httpx.HTTPStatusError` (4xx/5xx) → `LLMError("HTTP N")` · [app/llm/client.py:50-52](../app/llm/client.py)
- Парсинг упал (`KeyError`/`IndexError`) → `LLMError("Failed to parse")` · [app/llm/client.py:53-55](../app/llm/client.py)
- `httpx.ConnectError` → `LLMError("Cannot connect")` · [app/llm/client.py:56-58](../app/llm/client.py)

В `handle_message` эти ошибки ловятся:
- `LLMError` с `"404"` в сообщении → user message «Model '{model}' is not available» · [app/bot/handlers.py:142-147](../app/bot/handlers.py)
- Остальные `LLMError` → «Sorry, the language model is currently unavailable. Please try again later.» · [app/bot/handlers.py:148-151](../app/bot/handlers.py)
- Любое другое `Exception` → `logger.exception("unexpected_error")` + «An unexpected error occurred» · [app/bot/handlers.py:152-156](../app/bot/handlers.py)

---

## Flow 4 — `/models` command

**Trigger**: пользователь пишет `/models`.

1. `CommandHandler("models")` → `BotHandlers.models` · [app/bot/handlers.py](../app/bot/handlers.py)
2. `current = await self.users.get_model(user_id)` — fallback на default
3. `installed = await self.chat.list_models()` — фасад над `LLMClient.list_models` (handler не знает про `app.llm`) → HTTP GET `{base_url}/v1/models` · [app/chat/service.py](../app/chat/service.py) · [app/llm/client.py](../app/llm/client.py)
4. Если `installed` пустой → «No models installed. Ask admin to run: make pull-models»
5. Строятся `InlineKeyboardButton` для каждой модели, маркер `> ` перед текущей
6. `reply_text("Current model: X\nTap to switch:", reply_markup=InlineKeyboardMarkup)`

---

## Flow 5 — Inline keyboard tap (model switch)

**Trigger**: пользователь тапает кнопку из keyboard `/models`.

1. Telegram присылает `CallbackQuery` с `data="model:X"` → `CallbackQueryHandler(pattern=r"^model:")` → `BotHandlers.model_callback`
2. `query.answer()` — нативный dismiss loading spinner Telegram
3. `model_name = query.data.removeprefix("model:")`
4. `previous = await self.users.get_model(user_id)` — запомнить предыдущую модель (из YAML или default)
5. `await self.users.set_model(user_id, model_name)` — **persistent**: создаёт/обновляет запись в `data/users/{telegram_id}.yaml`, переживает рестарт (C-04, закрывает D-03)
6. Лог `model_changed` (user_id, username, previous_model, new_model)
7. Перерисовка inline keyboard:
   - `installed = await self.chat.list_models()` (через фасад)
   - `edit_message_text("Tap to switch:", reply_markup=...)` — обновление того же сообщения
8. Отправка отдельного сообщения `"Switched: {prev} → {new}"`

---

## Flow 6 — `/model <name>` command

**Trigger**: пользователь пишет `/model qwen3:1.7b`.

1. `CommandHandler("model")` → `BotHandlers.set_model`
2. Если `context.args` пустой → usage hint
3. `installed = await self.chat.list_models()` — через фасад
4. Если модель не в `installed` → user message с доступным списком
5. `previous = await self.users.get_model(user_id)`
6. `await self.users.set_model(user_id, model_name)` — persistent
7. Лог `model_changed` (те же поля, что и в Flow 5)
8. `reply_text(f"Switched: {previous} → {model_name}")`

---

## Flow 7 — `/start` / `/help`

**Trigger**: `/start` или `/help`.

1. `CommandHandler("start"|"help")` → `BotHandlers.start` (help просто перенаправляет на start)
2. Лог `command_start` (user_id, username)
3. `current = await self.users.get_model(user.id)`
4. `reply_text("Hello, {first_name}! ... Current model: {current} ... Commands: ...")`

> Примечание (C-05): `users.get_or_create` (вызывается из `users.set_model` → Flow 5/6) публикует `UserCreated(telegram_id, created_at)` для нового пользователя. Подписчиков пока нет — событие зафиксировано как контракт для будущих обработчиков (welcome-message flow, analytics).

---

## Flow 8 — `/reset` command

**Trigger**: пользователь пишет `/reset`.

1. `CommandHandler("reset")` → `BotHandlers.reset`
2. `await self.chat.reset_history(user.id)` — после C-05 публикует `HistoryResetRequested(telegram_id)` через bus. Подписчик `app/history/subscriber.py` зовёт `store.reset` (удаляет запись в cache + unlink файла `data/history/{user_id}.yaml`). Sequential publish гарантирует, что к моменту возврата файл удалён · [app/chat/service.py](../app/chat/service.py)
3. Лог `history_reset` (user_id, username)
4. `reply_text("История диалога очищена.")`

---

## Flow 9 — Shutdown

**Trigger**: `SIGINT` или `SIGTERM` (например, `docker compose down`).

1. `_signal_handler()` → лог `shutdown_signal_received` → `stop_event.set()` · [app/main.py:43-45](../app/main.py)
2. `await stop_event.wait()` возвращает управление
3. Лог `shutting_down`
4. `await app.updater.stop()` — остановка polling
5. `await app.stop()` — остановка Application
6. `finally: await llm.close()` — закрытие httpx клиента · [app/main.py:60-62](../app/main.py)
7. Лог `bot_stopped`

---

## Внешние зависимости

| Система | Как используется | Где | Контракт |
|---------|------------------|-----|----------|
| **Telegram Bot API** | python-telegram-bot polling mode, `getUpdates`, `sendMessage`, callback queries, chat actions | app/main.py, app/bot/handlers.py | [contracts/external/telegram.md](contracts/external/telegram.md) |
| **Lemonade** | OpenAI-compatible `/v1/chat/completions`, `/v1/models`. Запущен как отдельный проект (`../lemonade-server`), бот ходит к нему через shared docker-сеть `llm-net` | app/llm/client.py | [contracts/external/ollama.md](contracts/external/ollama.md) (имя файла историческое, контракт актуален) |
| `httpx` | HTTP клиент | app/llm/client.py | — |
| `structlog` | JSON логи | app/logging_config.py, везде | — |
| `pydantic-settings` | Env-based config | app/config.py | — |
| `PyYAML` | Сериализация per-user истории диалога + per-user state | app/history/store.py, app/users/store.py | — |

---

## Карта файлов и их ответственность (после C-05)

```
app/
├── main.py                  — entry point, DI wiring (EventBus → UserStore→UserService → HistoryStore + subscribe → ChatService → BotHandlers)
├── config.py                — Settings из .env
├── logging_config.py        — structlog configure
├── events/                  ← C-05: in-memory event bus, zero app-deps (только stdlib)
│   ├── bus.py               — EventBus (subscribe/publish, sequential await)
│   └── types.py             — frozen dataclasses: UserCreated, MessageReceived, ResponseGenerated, HistorySummarized, HistoryResetRequested
├── bot/                     ← транспорт Telegram, депенды только на users + chat
│   ├── handlers.py          — все Telegram хэндлеры + /reset (тонкие адаптеры)
│   └── middleware.py        — LoggingMiddleware
├── users/                   ← C-04 + C-05: идентификация + per-user state, persistent; публикует UserCreated
│   ├── models.py            — dataclass User {telegram_id, current_model, created_at}
│   ├── store.py             — UserStore (YAML per-user в data/users/{telegram_id}.yaml)
│   └── service.py           — UserService (get_or_create → bus.publish(UserCreated) для нового, get_model с default-fallback, set_model)
├── history/                 ← C-05: диалоговая история, подписчик 4 событий
│   ├── store.py             — HistoryStore (YAML per-user + cache + locks, count- + char-trim)
│   └── subscriber.py        — subscribe(bus, store): MessageReceived/ResponseGenerated → append; HistorySummarized → replace; HistoryResetRequested → reset
├── chat/                    ← C-04 + C-05: use-case слой; больше не импортит app.history
│   ├── service.py           — ChatService (reply: orchestrates users + history.get + summarizer + llm + публикует MessageReceived/ResponseGenerated/HistorySummarized; reset_history публикует HistoryResetRequested); HistoryReader Protocol
│   └── summarizer.py        — Summarizer (D-06 LLM-based summary; перенесён из history/ в C-04)
└── llm/                     ← тонкий HTTP-адаптер к Lemonade
    └── client.py            — LLMClient + LLMError
```

**Архитектурные правила** (enforced grep'ом, C-04/C-05 success criteria):
- `bot/` импортит только `app.users` и `app.chat`
- `chat/` НЕ импортит `app.history` (чтение через `HistoryReader` Protocol, запись через события)
- `users/` импортит только `app.events` (для публикации UserCreated)
- `history/` импортит только `app.events` (для подписки)
- `llm/` импортит только `app.config`
- `events/` — zero app-deps (только stdlib)
- `LLMError` ре-экспортируется из `app.chat`, чтобы handler не лез в `app.llm.client`

**События как контракт** (C-05): все state-mutations над историей идут через bus. Чтобы добавить аналитику, persistence событий, второго подписчика — достаточно зарегистрировать handler в `main.py`, исходные модули не меняются.

Тесты: `tests/test_llm_client.py` (6) + `tests/test_history_store.py` (15) + `tests/test_summarizer.py` (8) + `tests/test_user_store.py` (8) + `tests/test_user_service.py` (9) + `tests/test_chat_service.py` (11) + `tests/test_event_bus.py` (6) + `tests/test_history_subscriber.py` (6) = **69**.
