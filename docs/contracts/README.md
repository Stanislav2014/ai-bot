# Contracts

Формальные описания внешних интерфейсов, с которыми взаимодействует ai-bot.

## Структура

```
contracts/
├── README.md            — этот файл
└── external/            — внешние системы
    ├── telegram.md      — Telegram Bot API
    └── ollama.md        — Ollama / Lemonade OpenAI-compatible API
```

Секций `api/` (входящие REST) и `events/` (очереди) нет — у ai-bot нет собственного HTTP endpoint и нет очередей.

## Что должно быть в файле `external/<system>.md`

- **Direction** — входящие / исходящие вызовы
- **Protocol** — HTTP / HTTPS / WebSocket / polling
- **SDK / library** — что используется в коде
- **Use cases** — какие операции и зачем
- **Configuration** — env vars, .env ключи
- **Auth mechanism** — как авторизуемся
- **Gotchas** — rate limits, security, edge cases
- **Related code** — ссылки на файлы с `file:line`
- **History** — изменения контракта (если были breaking changes)
