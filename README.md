# AI Bot — Telegram Bot with Local LLM

Telegram-бот, работающий с локальными языковыми моделями через Ollama.

## LLM

Используется **Ollama** с моделями:
- `qwen3:0.6b` (легкая)
- `qwen3.5:27b` (мощная)
- `gpt-oss-20b`

## Как сгенерирован код

Код сгенерирован с помощью Claude (Anthropic) с последующей доработкой и code review.

## Быстрый старт

### 1. Настройка

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN (получить у @BotFather)
```

### 2. Запуск через Docker

```bash
make build
make up
make pull-models   # скачать модели в Ollama
make logs          # смотреть логи
```

### 3. Запуск локально (без Docker)

```bash
pip install -r requirements.txt
# Убедитесь что Ollama запущен: ollama serve
python -m app.main
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/help` | Помощь |
| `/models` | Список доступных моделей |
| `/model <name>` | Сменить модель |
| `/stats` | Статистика промптов |

## Makefile

| Команда | Описание |
|---------|----------|
| `make build` | Сборка Docker-образа |
| `make up` | Запуск |
| `make down` | Остановка |
| `make logs` | Логи бота |
| `make test` | Тесты |
| `make lint` | Линтинг |
| `make pull-models` | Скачать модели |

## Деплой

```bash
./deploy.sh
```

## Архитектура

```
Telegram → Bot (python-telegram-bot) → Ollama API → Bot → Telegram
                    ↓
              SQLite (prompt logs)
```

Каждое сообщение обрабатывается независимо, без хранения истории диалога.
Все промпты и ответы логируются в SQLite для статистики.

## Разработка

```bash
pip install -r requirements-dev.txt
make test
make lint
```
