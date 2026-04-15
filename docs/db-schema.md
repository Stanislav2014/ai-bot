# Database Schema

## Текущее состояние: **без БД, с файловой персистенцией**

ai-bot **не использует базу данных**. Часть состояния (история диалога) хранится в YAML-файлах per-user, что проще чем SQLite для текущего scope.

## Что где хранится

| Данные | Где | Lifetime |
|--------|-----|----------|
| История диалога per-user | `data/history/{user_id}.yaml` — YAML list `{role, content}` | Persistent (docker volume `./data:/app/data`) |
| Выбранная модель per-user | `BotHandlers.user_models` — Python `dict[int, str]` | До рестарта процесса (см. [legacy-warning § 4](legacy-warning.md#4-user_models--per-user-модель-в-памяти-процесса)) |
| Логи | stdout (structlog JSON) → Docker logs | По ротации docker |
| Секреты (токен) | `.env` файл в git-ignored | Persistent, manual |
| Кеш моделей Lemonade | `lemonade_cache` docker volume | Persistent |

## Почему нет БД

- **Простота** — нет миграций, нет ORM, нет schema versioning
- **По спеке** — оригинальное ТЗ требовало «без базы данных и без хранения состояния»
- **Нет нагрузки** — бот для одного-нескольких пользователей

## Когда может понадобиться

См. [discuss.md § 1](discuss.md#1-persistence-для-per-user-selected-model) и [discuss.md § 2](discuss.md#2-dialog-history).

Если решение — **да, нужна**, обсудить на уровне [discuss.md](discuss.md) перед реализацией. Кандидаты:
- **Легкий JSON-файл** на диске (`data/user_models.json`) — если нужен только persistent model selection
- **SQLite + aiosqlite** (или SQLAlchemy) — если появляется история диалогов, статистика, allowlist
- **Redis** — если когда-нибудь multi-instance deploy (но это очень далеко)

## Файловая система

Пути, используемые проектом:

| Путь | Назначение | В git? |
|------|-----------|--------|
| `/app/data/` | Зарезервировано под persistent файлы (сейчас пусто) — создаётся в Dockerfile | — |
| `/root/.cache` в контейнере `lemonade` | Кеш моделей Lemonade (docker volume `lemonade_cache`) | — |
| `.env` | Runtime config / секреты | Нет (`.gitignore`) |

[Dockerfile строка 8](../Dockerfile) — `mkdir -p /app/data && chown botuser:botuser /app/data`.
