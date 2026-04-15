# Context Dump — карта взаимодействий

Технический атлас: как именно компоненты взаимодействуют. Обновлять после каждого значимого исследования. Все ссылки в формате `file:line`.

---

## Flow 1 — Startup

**Trigger**: `python -m app.main` (или `docker compose up`)

1. `main()` → `asyncio.run(run())` · [app/main.py:65-66](../app/main.py)
2. `setup_logging()` → structlog configure JSON renderer · [app/logging_config.py:9](../app/logging_config.py)
3. `settings` инстанцируется из `.env` (pydantic-settings) · [app/config.py:4](../app/config.py)
4. Создаётся `LLMClient` (httpx AsyncClient с timeout) · [app/llm/client.py:16-19](../app/llm/client.py)
5. Создаётся `BotHandlers(llm=llm)` с пустым `user_models = {}` · [app/bot/handlers.py:14-16](../app/bot/handlers.py)
6. `ApplicationBuilder().token(...).build()` — python-telegram-bot Application · [app/main.py:22](../app/main.py)
7. Регистрация handlers:
   - `LoggingMiddleware` (group=-1, всегда первый) · [app/main.py:25](../app/main.py)
   - `CommandHandler("start" | "help" | "models" | "model")` · [app/main.py:28-31](../app/main.py)
   - `CallbackQueryHandler(pattern=r"^model:")` для inline buttons · [app/main.py:34](../app/main.py)
   - `MessageHandler(filters.TEXT & ~filters.COMMAND)` — catch-all текст · [app/main.py:37](../app/main.py)
8. Signal handlers: `SIGINT`, `SIGTERM` → `stop_event.set()` · [app/main.py:43-48](../app/main.py)
9. `async with app: app.start() → app.updater.start_polling() → stop_event.wait()` · [app/main.py:53-56](../app/main.py)
10. При сигнале: `updater.stop() → app.stop() → llm.close()` · [app/main.py:58-61](../app/main.py)

---

## Flow 2 — Incoming text message (happy path)

**Trigger**: пользователь пишет текст боту в Telegram.

1. `Update` приходит через polling в `Application` dispatcher
2. **LoggingMiddleware.check_update()** проверяет — логирует `incoming_message` (user_id, username, chat_id, text[:200], message_id), возвращает `False` (не поглощает update) · [app/bot/middleware.py:18-29](../app/bot/middleware.py)
3. `MessageHandler(TEXT & ~COMMAND)` → `BotHandlers.handle_message` · [app/bot/handlers.py:112](../app/bot/handlers.py)
4. Resolve `model = self._get_model(user_id)` → `user_models.get(user_id, settings.default_model)` · [app/bot/handlers.py:158-159](../app/bot/handlers.py)
5. Лог `user_message` (user_id, username, model, text_length) · [app/bot/handlers.py:120-126](../app/bot/handlers.py)
6. Строится `messages = [{system}, {user}]` — **без истории** · [app/bot/handlers.py:129-132](../app/bot/handlers.py)
7. `chat.send_action("typing")` — Telegram показывает индикатор
8. `llm.chat(messages, model=model)` → HTTP POST `{base_url}/v1/chat/completions` с body `{model, messages, stream: false}` · [app/llm/client.py:24-42](../app/llm/client.py)
9. Лог `llm_request` (model, messages_count) → реально уходит в Lemonade
10. Lemonade обрабатывает → возвращает JSON choices/message/content
11. `LLMClient.chat()` парсит `data["choices"][0]["message"]["content"]` и `data["usage"]["total_tokens"]` · [app/llm/client.py:42-45](../app/llm/client.py)
12. Лог `llm_response` (model, tokens) · [app/llm/client.py:44](../app/llm/client.py)
13. `handle_message` получает `{content, tokens_used}`, логирует `llm_reply` (user_id, model, reply_length) · [app/bot/handlers.py:139](../app/bot/handlers.py)
14. `message.reply_text(content)` → отправка обратно в Telegram

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

1. `CommandHandler("models")` → `BotHandlers.models` · [app/bot/handlers.py:34](../app/bot/handlers.py)
2. `current = self._get_model(user_id)`
3. `installed = await self.llm.list_models()` → HTTP GET `{base_url}/v1/models` · [app/llm/client.py:60-70](../app/llm/client.py)
4. Если `installed` пустой → «No models installed. Ask admin to run: make pull-models»
5. Строятся `InlineKeyboardButton` для каждой модели, маркер `> ` перед текущей · [app/bot/handlers.py:45-47](../app/bot/handlers.py)
6. `reply_text("Current model: X\nTap to switch:", reply_markup=InlineKeyboardMarkup)` · [app/bot/handlers.py:49-52](../app/bot/handlers.py)

---

## Flow 5 — Inline keyboard tap (model switch)

**Trigger**: пользователь тапает кнопку из keyboard `/models`.

1. Telegram присылает `CallbackQuery` с `data="model:X"` → `CallbackQueryHandler(pattern=r"^model:")` → `BotHandlers.model_callback` · [app/bot/handlers.py:54](../app/bot/handlers.py)
2. `query.answer()` — нативный dismiss loading spinner Telegram
3. `model_name = query.data.removeprefix("model:")`
4. `previous = self._get_model(user_id)` — запомнить предыдущую модель
5. `self.user_models[user_id] = model_name` — обновление in-memory dict · [app/bot/handlers.py:64](../app/bot/handlers.py)
6. Лог `model_changed` (user_id, username, previous_model, new_model) · [app/bot/handlers.py:65-71](../app/bot/handlers.py)
7. Перерисовка inline keyboard:
   - `installed = await self.llm.list_models()` (ещё HTTP вызов!)
   - `edit_message_text("Tap to switch:", reply_markup=...)` — обновление того же сообщения · [app/bot/handlers.py:74-83](../app/bot/handlers.py)
8. Отправка отдельного сообщения `"Switched: {prev} → {new}"` (исторически добавлено — юзер хотел явное подтверждение) · [app/bot/handlers.py:84](../app/bot/handlers.py)

---

## Flow 6 — `/model <name>` command

**Trigger**: пользователь пишет `/model qwen3:1.7b`.

1. `CommandHandler("model")` → `BotHandlers.set_model` · [app/bot/handlers.py:86](../app/bot/handlers.py)
2. Если `context.args` пустой → usage hint
3. `installed = await self.llm.list_models()` — HTTP
4. Если модель не в `installed` → user message с доступным списком
5. `previous = self._get_model(user_id)`
6. `self.user_models[user_id] = model_name`
7. Лог `model_changed` (те же поля, что и в flow 5) · [app/bot/handlers.py:103-109](../app/bot/handlers.py)
8. `reply_text(f"Switched: {previous} → {model_name}")`

---

## Flow 7 — `/start` / `/help`

**Trigger**: `/start` или `/help`.

1. `CommandHandler("start"|"help")` → `BotHandlers.start` (help просто перенаправляет на start) · [app/bot/handlers.py:18, 29-32](../app/bot/handlers.py)
2. Лог `command_start` (user_id, username)
3. `reply_text("Hello, {first_name}! ... Current model: X ... Commands: ...")` · [app/bot/handlers.py:21-27](../app/bot/handlers.py)

---

## Flow 8 — Shutdown

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
| **Lemonade / Ollama** | OpenAI-compatible `/v1/chat/completions`, `/v1/models` | app/llm/client.py | [contracts/external/ollama.md](contracts/external/ollama.md) |
| `httpx` | HTTP клиент | app/llm/client.py | — |
| `structlog` | JSON логи | app/logging_config.py, везде | — |
| `pydantic-settings` | Env-based config | app/config.py | — |

---

## Карта файлов и их ответственность

```
app/
├── main.py                  — entry point, setup, signal handling (70 строк)
├── config.py                — Settings из .env (14 строк)
├── logging_config.py        — structlog configure (25 строк)
├── bot/
│   ├── handlers.py          — все Telegram хэндлеры (159 строк)
│   └── middleware.py        — LoggingMiddleware (29 строк)
└── llm/
    └── client.py            — LLMClient + LLMError (74 строки)
```

Общий размер: ~370 строк production кода. Тестов: ~50 строк (на client.py).
