# Telegram Bot API

**Direction**: исходящие (polling) + ответы пользователям

**Protocol**: HTTPS, long-polling через `python-telegram-bot` v21

**SDK / library**: `python-telegram-bot==21.9`

## Use cases

| Операция | Где в коде |
|----------|-----------|
| Polling updates (`getUpdates`) | [app/main.py:55](../../../app/main.py) `app.updater.start_polling()` |
| Отправка текстового сообщения | [app/bot/handlers.py:21, 84, 110, 140](../../../app/bot/handlers.py) `message.reply_text(...)` |
| Inline keyboard в сообщении | [app/bot/handlers.py:49-52, 80-83](../../../app/bot/handlers.py) `InlineKeyboardMarkup([...])` |
| Edit сообщения (inline rebuild) | [app/bot/handlers.py:80](../../../app/bot/handlers.py) `query.edit_message_text(...)` |
| Callback query answer | [app/bot/handlers.py:58](../../../app/bot/handlers.py) `query.answer()` |
| Typing indicator | [app/bot/handlers.py:135](../../../app/bot/handlers.py) `chat.send_action("typing")` |

## Регистрируемые хэндлеры

| Тип | Pattern | Callback |
|-----|---------|----------|
| `CommandHandler` | `start` | `BotHandlers.start` |
| `CommandHandler` | `help` | `BotHandlers.help_command` |
| `CommandHandler` | `models` | `BotHandlers.models` |
| `CommandHandler` | `model` | `BotHandlers.set_model` |
| `CallbackQueryHandler` | `^model:` | `BotHandlers.model_callback` |
| `MessageHandler` | `TEXT & ~COMMAND` | `BotHandlers.handle_message` |
| `LoggingMiddleware` (group=-1) | все updates | `_noop` (только `check_update` логирует) |

## Configuration

| Env | Где |
|-----|-----|
| `TELEGRAM_BOT_TOKEN` | [.env](../../../.env) (get от @BotFather) |

`ApplicationBuilder().token(settings.telegram_bot_token).build()` — [app/main.py:22](../../../app/main.py).

## Auth

- Bot token в header запросов (`python-telegram-bot` делает это под капотом)
- Нет allowlist пользователей — любой, кто знает username бота, может слать сообщения. См. [discuss.md § 4](../../discuss.md#4-auth--access-control).

## Callback data format

- Все inline buttons используют префикс `model:` + имя модели
- Пример: `model:qwen3:0.6b` → `CallbackQueryHandler(pattern=r"^model:")` ловит, хэндлер делает `removeprefix("model:")`
- **Важно**: имя модели может содержать `:`, поэтому splitить по `:` **нельзя** — использовать `removeprefix`

## Gotchas

- **Polling vs webhook** — используется polling. Webhook не настроен (нет публичного HTTPS у бота).
- **`query.answer()` обязательно до любого edit** — иначе у пользователя висит «processing» анимация до таймаута.
- **`edit_message_text` fails если текст не изменился** — потому `"Tap to switch:"` используется как неизменяемый текст, keyboard обновляется через `reply_markup`.
- **Rate limits** — Telegram ограничивает исходящие: ~30 сообщений/сек на всех, 1 сообщение/сек на chat. Не достигается на текущей нагрузке.
- **Message length** — лимит 4096 символов. Длинные LLM ответы → `BadRequest`. См. [legacy-warning.md § 7](../../legacy-warning.md#7-длинные-llm-ответы--4096-символов-сломают-reply_text).
- **Typing action** — автоматически истекает через 5 секунд. Для длинных запросов нужно переотправлять (сейчас не делаем).
- **Graceful shutdown** — `await app.updater.stop() → await app.stop()`, иначе polling остаётся висеть. [app/main.py:58-59](../../../app/main.py).

## Related code

- [app/main.py](../../../app/main.py) — setup, регистрация, polling loop
- [app/bot/handlers.py](../../../app/bot/handlers.py) — все интеракции
- [app/bot/middleware.py](../../../app/bot/middleware.py) — логирование входящих

## History

- 2026-04-09 — первая реализация (text commands + messages)
- 2026-04-10 — inline keyboard для model switching ([commits f5de296, 609e241, b0b0dd0](../../../README.md))
