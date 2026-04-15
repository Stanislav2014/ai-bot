# Идеи (ещё не задачи)

Сюда пишем всё что приходит в голову, но пока не стало задачей. Периодически чистить — что-то перейдёт в [plan.md](plan.md) / [tasks.md](tasks.md), что-то — в мусор.

## UX

- Команда `/reset` — очистить выбранную модель, вернуться к дефолту
- Кнопка «пересобрать ответ» (retry с той же моделью / другой моделью)
- Индикатор прогресса для длинных запросов (промежуточные typing действия)
- Markdown / HTML форматирование ответов LLM (сейчас plain text)
- Команда `/prompt` — сменить system prompt per-user

## Tech

- Кеш `list_models()` — сейчас вызывается на каждом `/models` и при каждом переключении
- Health check endpoint для docker healthcheck директивы
- Retry с exponential backoff для временных сбоев LLM
- Опциональное логирование содержимого промптов в файл (сейчас только stdout)
- Метрики (prometheus?) — tokens_used, latency, errors per model

## Delivery

- CI/CD (GitHub Actions) — tests + ruff + build на каждый push
- Telegram notification в отдельный канал при деплое
- Автоматическое обновление моделей по cron

## Research

- Streaming ответы — проверить нужно ли и как это скажется на логировании
- Multi-turn контекст — сколько сообщений безопасно хранить в памяти без БД
