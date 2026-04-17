# AI Bot — Telegram Bot with Local LLM

Telegram-бот, работающий с локальными языковыми моделями через **Lemonade Server** (OpenAI-compatible). Хранит историю диалога per-user, сжимает старый контекст через суммаризацию, configurable persona.

Sprint 1 закрыт 2026-04-17 — 9 задач. См. [docs/sprint-1-delivery.md](docs/sprint-1-delivery.md) и [docs/dialogs/](docs/dialogs/) для деталей и живых примеров.

## LLM

**Lemonade Server** (OpenAI-compatible API) с qwen3-семейством моделей:
- `Qwen3-0.6B-GGUF` (default, лёгкая, ~1-2с latency)
- `Qwen3-4B-Instruct-2507-GGUF` (средняя)
- `Qwen3-8B-GGUF` (крупная, лучше качество для follow-up)

Модель переключается per-user через `/models` (inline keyboard).

## Как сгенерирован код

Код сгенерирован с помощью Claude (Anthropic) с последующей доработкой через TDD и code review. Полная история работы и все промты — в [docs/prompts-sprint-1.md](docs/prompts-sprint-1.md).

## Быстрый старт

### 1. Настройка

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN (получить у @BotFather)
# При желании поправьте SYSTEM_PROMPT, HISTORY_*, LOG_FILE — все описаны в .env.example
```

### 2. Запуск через Docker

```bash
make build
make up
make pull-models   # скачать дефолтную модель через Lemonade CLI
make list-models   # показать установленные модели
make logs          # смотреть логи в реальном времени
```

### 3. Запуск локально (без Docker)

```bash
pip install -r requirements.txt
# Запусти Lemonade server отдельно (docker или native)
python -m app.main
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и список команд |
| `/help` | Помощь |
| `/models` | Inline keyboard для переключения модели |
| `/model <name>` | Переключить модель по имени |
| `/reset` | Очистить историю диалога (per-user) |

## Архитектура

```
Telegram → Bot (polling) → [HistoryStore + Summarizer] → Lemonade API → Bot → Telegram
                                    ↓
                         data/history/{user_id}.yaml  (память per-user)
```

Ключевые фичи (Sprint 1):
- **Per-user dialog history** (D-04) — YAML файл per пользователь, follow-up запросы работают
- **Двойной safeguard** (D-05) — trim по сообщениям + trim по символам, защита от context overflow
- **LLM-суммаризация** (D-06) — старые сообщения сжимаются в одно резюме, fail-safe
- **Configurable persona** (D-07) — `SYSTEM_PROMPT` env, дефолт «опытный программист»
- **Context observability** (D-08) — весь LLM payload в логе перед отправкой
- **Dual logging** (D-09) — `data/logs/bot.log` + stdout, ротация 10MB × 5
- **Stateless toggle** (D-10) — `HISTORY_ENABLED=false` → бот полностью забывает между сообщениями

Подробно: [docs/architecture.md](docs/architecture.md), [docs/context-dump.md](docs/context-dump.md).

## Документация

- [docs/README.md](docs/README.md) — индекс всей документации
- [docs/sprint-1-delivery.md](docs/sprint-1-delivery.md) — финальный delivery-документ Sprint 1
- [docs/dialogs/](docs/dialogs/) — скриншоты реальных диалогов (stateless vs context)
- [docs/tasks/](docs/tasks/) — спеки всех задач D-04…D-10, C-01/C-02
- [docs/architecture.md](docs/architecture.md) — архитектурные паттерны + edge cases
- [docs/tech-stack.md](docs/tech-stack.md) — env-переменные и зависимости

## Makefile

| Команда | Описание |
|---------|----------|
| `make build` | Сборка Docker-образа |
| `make up` | Запуск |
| `make down` | Остановка |
| `make restart` | Пересоздать `bot` контейнер с новой конфигурацией |
| `make logs` | Live-логи бота (stdout через `docker compose logs -f`) |
| `make test` | Прогон тестов (pytest-asyncio) |
| `make lint` | Линт (ruff) |
| `make lint-fix` | Автофикс линт-нарушений |
| `make pull-models` | Скачать дефолтную модель в Lemonade |
| `make list-models` | Список установленных моделей в Lemonade |
| `make shell` | Shell в контейнер бота |
| `make clean` | Остановить + удалить volumes |

## Деплой

```bash
./deploy.sh
```

## Разработка

```bash
pip install -r requirements-dev.txt
make test    # 29 unit tests: pytest-asyncio
make lint    # ruff check
```

Workflow TDD + branch conventions — см. [docs/instructions.md](docs/instructions.md).

## Логи

```bash
make logs                                        # stdout через docker-compose
tail -f data/logs/bot.log                        # файл внутри проекта (D-09)
cat data/logs/bot.log | grep llm_request         # все LLM-запросы с полным контекстом
```

## Stateless mode (для A/B-теста)

```bash
# В .env:
HISTORY_ENABLED=false

make restart
# Теперь бот забывает между сообщениями. См. docs/dialogs/stateless-vs-context-2026-04-17.png
```
