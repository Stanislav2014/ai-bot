# Telegram Bot с локальной LLM — Спецификация

## Обзор

Telegram-бот, работающий с локальными LLM-моделями через OpenAI-совместимый API (Ollama).
Поддерживаемые модели: gpt-oss-20b (default), qwen3-0.6b, qwen3.5-27b.

## Функциональные требования

### 1. Telegram Bot
- Приём текстовых сообщений от пользователей
- Команды: `/start`, `/help`, `/model <name>` (смена модели), `/models` (список), `/stats` (статистика промптов)
- Ответ генерируется через локальную LLM
- Поддержка контекста беседы (последние N сообщений, настраивается)

### 2. LLM Integration
- Подключение к Ollama через OpenAI-совместимый API (`/v1/chat/completions`)
- Переключение между моделями на лету (per-user)
- Таймаут запросов к LLM (настраивается)
- Streaming-ответы не используем (для простоты логирования)

### 3. Логирование промптов
- **Все** промпты пользователей и ответы LLM сохраняются в SQLite
- Таблица `prompt_logs`: id, user_id, username, model, prompt, response, tokens_used, created_at
- Эндпоинт статистики через команду `/stats` (кол-во промптов, по моделям)
- Логи приложения — structlog в JSON-формате в stdout + файл

### 4. Обработка ошибок
- Все запросы к LLM обёрнуты в try/except
- Пользователь получает понятное сообщение при ошибке
- Ошибки логируются с полным traceback
- Graceful shutdown

### 5. Безопасность
- Токены и секреты ТОЛЬКО в `.env` файле
- `.env` в `.gitignore`
- `.env.example` с описанием переменных (без значений)

## Архитектура

```
ai-bot/
├── app/
│   ├── __init__.py
│   ├── main.py           # Entry point
│   ├── config.py          # Pydantic settings from .env
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py    # Telegram command & message handlers
│   │   └── middleware.py   # Logging middleware
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py      # OpenAI-compatible client for Ollama
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py      # SQLAlchemy models
│   │   └── repository.py  # CRUD operations
│   └── logging_config.py  # structlog setup
├── tests/
│   ├── __init__.py
│   ├── test_handlers.py
│   ├── test_llm_client.py
│   └── test_db.py
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── deploy.sh
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Стек технологий

- **Python 3.11+**
- **python-telegram-bot** — Telegram API
- **httpx** — HTTP-клиент для Ollama API
- **SQLAlchemy + aiosqlite** — async SQLite ORM
- **pydantic-settings** — конфигурация из .env
- **structlog** — structured logging
- **pytest + pytest-asyncio** — тесты
- **Docker + docker-compose** — контейнеризация
- **Make** — команды разработки

## Конфигурация (.env)

```
TELEGRAM_BOT_TOKEN=
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL=gpt-oss-20b
CONTEXT_MESSAGES_LIMIT=10
LLM_TIMEOUT=120
LOG_LEVEL=INFO
DB_PATH=data/prompts.db
```

## Docker

- `docker-compose.yml` поднимает бот + Ollama
- Volume для SQLite данных и моделей Ollama
- Network для связи контейнеров

## Makefile команды

- `make build` — сборка Docker-образа
- `make up` — запуск через docker-compose
- `make down` — остановка
- `make logs` — просмотр логов
- `make test` — запуск тестов
- `make lint` — линтинг (ruff)
- `make shell` — shell в контейнер бота
- `make pull-models` — скачивание моделей в Ollama

## Deploy

`deploy.sh` — скрипт для деплоя на сервер:
1. Pull latest code
2. Build images
3. Pull models (if not present)
4. Restart services
