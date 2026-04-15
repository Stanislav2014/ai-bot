# ai-bot — Telegram bot with Local LLM

## Назначение

Telegram-бот, который работает как простой AI-чат, используя локальную LLM (через OpenAI-совместимый API — Ollama / Lemonade / vLLM). Каждое сообщение — независимый запрос без истории диалога. Каждый пользователь может переключать модель через inline-клавиатуру.

## Продукты / аудитория

- **Пользователь**: любой участник Telegram-чата с ботом
- **Оператор**: владелец сервера, где развёрнут бот + локальный LLM-сервер

## Стек (кратко)

- Python 3.11+, python-telegram-bot 21.9 (polling)
- httpx async (OpenAI-compatible `/v1/chat/completions`)
- pydantic-settings, structlog (JSON), pytest + pytest-asyncio, ruff
- Docker Compose: `bot` + `lemonade` (LLM server, OpenAI-compatible)
- Детали: [tech-stack.md](tech-stack.md)

## Карта «где что искать»

| Нужно | Смотреть |
|-------|----------|
| Как устроен flow сообщения | [context-dump.md](context-dump.md) |
| Почему так, а не иначе | [architecture.md](architecture.md) |
| Тех-долг / known issues | [legacy-warning.md](legacy-warning.md) |
| Стек и версии | [tech-stack.md](tech-stack.md) |
| Команды бота | [ui-kit.md](ui-kit.md) |
| API контракты | [contracts/](contracts/) |
| Текущая работа | [current-sprint.md](current-sprint.md) |
| Все задачи | [tasks.md](tasks.md) |

## Ключевые принципы

1. **Stateless** — нет БД, нет истории диалога между сообщениями. Per-user selected model хранится в памяти процесса (теряется при рестарте, это осознанный выбор).
2. **Local-first** — все модели локальные, никаких внешних LLM провайдеров.
3. **Observability** — все входящие сообщения и LLM-запросы логируются через structlog (JSON).
4. **Graceful errors** — все ошибки обёрнуты, пользователь получает понятное сообщение.
5. **Secrets only in .env** — `.env` в `.gitignore`, `.env.example` — образец без значений.

## Точки входа

- Entry point: [app/main.py](../app/main.py) — setup + polling loop
- Config: [app/config.py](../app/config.py) — pydantic settings
- Handlers: [app/bot/handlers.py](../app/bot/handlers.py)
- LLM client: [app/llm/client.py](../app/llm/client.py)

## Статус

MVP развёрнут и работает. Активной разработки нет, поддержка по мере появления issues.
