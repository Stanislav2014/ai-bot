# Technology Stack

## Runtime

- **Python 3.11+** (использует `logging.getLevelNamesMapping()` — 3.11+)
- Docker (образ `python:3.11-slim`)

## Runtime-зависимости

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `python-telegram-bot` | 21.9 | Telegram Bot API клиент + хэндлеры + polling |
| `httpx` | 0.28.1 | Async HTTP клиент для LLM API |
| `pydantic-settings` | 2.7.1 | Env-based config (.env → Settings) |
| `structlog` | 24.4.0 | Structured JSON логирование |
| `PyYAML` | 6.0.2 | Persistent dialog history (YAML per-user) |

[requirements.txt](../requirements.txt)

## Dev-зависимости

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `ruff` | 0.8.6 | Линтер (форматер не используется) |
| `pytest` | 8.3.4 | Тестовый фреймворк |
| `pytest-asyncio` | 0.25.0 | Async тесты |

[requirements-dev.txt](../requirements-dev.txt)

## Infrastructure

| Компонент | Назначение |
|-----------|-----------|
| **Docker Compose** | `bot` + `lemonade` сервисы |
| **Lemonade** | Локальный LLM сервер с OpenAI-compatible API (Dockerfile в `lemonade/`) |
| **Makefile** | Обёртки над docker compose и dev-командами |
| **deploy.sh** | Pull-build-up + проверка моделей |

[docker-compose.yml](../docker-compose.yml) · [Dockerfile](../Dockerfile) · [Makefile](../Makefile) · [deploy.sh](../deploy.sh)

## Внешние сервисы (runtime)

| Сервис | Протокол | Зачем |
|--------|----------|-------|
| Telegram Bot API | HTTPS long-polling | Приём сообщений, отправка ответов |
| Lemonade / Ollama / vLLM | HTTP OpenAI-compatible | `/v1/chat/completions`, `/v1/models` |

## Dev-porty

| Порт | Сервис |
|------|--------|
| 8000 | Lemonade (внутри docker-сети) — пробрасывается наружу docker-compose.yml |
| — | Бот не слушает порты (polling mode, исходящие соединения только) |

## Config через env

Конфигурация — `.env` файл, парсится через pydantic-settings. См. [.env.example](../.env.example).

| Переменная | Default | Назначение |
|-----------|---------|-----------|
| `TELEGRAM_BOT_TOKEN` | — (обязательно) | Токен от @BotFather |
| `LLM_BASE_URL` | `http://ollama:11434` (в коде) / `http://lemonade:8000/api` (в .env.example) | Base URL OpenAI-compatible API ⚠ см. [legacy-warning.md § 1](legacy-warning.md#1-ollama--lemonade-несогласованность) |
| `DEFAULT_MODEL` | `qwen3:0.6b` (в коде) / `Qwen3-0.6B-GGUF` (в .env.example) | Дефолтная модель |
| `LLM_TIMEOUT` | 120 | Секунд таймаут на LLM запрос |
| `LOG_LEVEL` | INFO | Уровень structlog |
| `HISTORY_DIR` | `data/history` | Папка с YAML файлами истории per-user |
| `HISTORY_MAX_MESSAGES` | 20 | Макс сообщений в истории (0 = без лимита) |
| `HISTORY_MAX_CHARS` | 8000 | Макс суммарная длина истории в символах (0 = без лимита). Второй safeguard поверх `HISTORY_MAX_MESSAGES` |
| `HISTORY_SUMMARIZE_THRESHOLD` | 5 | Суммаризировать при `len(history) > threshold` (0 = disabled) |
| `HISTORY_KEEP_RECENT` | 2 | Сколько последних raw сообщений сохранить после суммаризации |
| `HISTORY_SUMMARIZE_MODEL` | `""` | Модель для summary LLM-запроса (пусто = `DEFAULT_MODEL`) |
| `SYSTEM_PROMPT` | `"Ты опытный программист и отвечаешь кратко и по делу."` | System prompt (persona бота), prepend-ится в каждый LLM-запрос |
| `LOG_CONTEXT_FULL` | `true` | Логировать полный `messages` payload в `llm_request` event. Metadata (total_chars/estimated_tokens) логируется всегда. Отключить в prod при росте логов |

## Python version constraint

- `logging.getLevelNamesMapping()` добавлена в **Python 3.11**. Это делает 3.11 минимальной версией.
- Docker образ фиксированный `python:3.11-slim`.
- `pyproject.toml` — см. его содержимое; явно не прибит, но все зависимости совместимы 3.11+.
