# UI Kit — Telegram UX

ai-bot — текстовый Telegram интерфейс. «UI» здесь это:
- Команды
- Тексты сообщений от бота
- Inline-клавиатура для выбора модели

Нет web UI, нет мобильного UI.

---

## Команды

| Команда | Что делает | Handler |
|---------|------------|---------|
| `/start` | Приветствие, показ текущей модели, список команд | [BotHandlers.start](../app/bot/handlers.py#L18) |
| `/help` | Alias на `/start` | [BotHandlers.help_command](../app/bot/handlers.py#L29) |
| `/models` | Inline-клавиатура со всеми установленными моделями | [BotHandlers.models](../app/bot/handlers.py#L34) |
| `/model <name>` | Переключить модель по имени (text-based) | [BotHandlers.set_model](../app/bot/handlers.py#L86) |

Любой другой текст (не команда) → LLM запрос.

---

## Тексты сообщений бота

### `/start` / `/help`
```
Hello, {first_name}! I'm a local LLM bot.

Current model: {model}

Commands:
/models — choose a model
/help — show this message
```

### `/models` — есть модели
```
Current model: {model}
Tap to switch:
[inline keyboard с кнопками]
```

### `/models` — нет моделей
```
No models installed. Ask admin to run: make pull-models
```

### `/model <name>` — без аргумента
```
Usage: /model <name>
Or use /models for buttons.
```

### `/model <name>` — модель не установлена
```
Model '{name}' is not installed.

Available: {list}
```

### `/model <name>` / inline tap — успех
```
Switched: {previous} → {new}
```

### LLM error — 404 (модель не доступна)
```
Model '{model}' is not available. Use /models to see installed models.
```

### LLM error — generic
```
Sorry, the language model is currently unavailable. Please try again later.
```

### LLM error — unexpected (catch-all)
```
An unexpected error occurred. Please try again later.
```

---

## Inline-клавиатура для выбора модели

Используется `InlineKeyboardMarkup` из python-telegram-bot.

### Схема
- Один столбец, одна модель на строку
- Кнопка с текущей моделью помечена префиксом `> ` (пробел после `>` обязателен)
- `callback_data` = `"model:{model_name}"` (префикс разбирается через `removeprefix`)
- После тапа: keyboard перерисовывается (маркер переезжает на новую модель) + отдельное сообщение `Switched: X → Y`

### Пример рендера (current = `qwen3:0.6b`)
```
[ > qwen3:0.6b    ]
[   qwen3:1.7b    ]
[   gpt-oss-20b   ]
```

### Особенности
- Модели сортируются алфавитно (`sorted(installed)`)
- При отсутствии моделей keyboard не показывается вообще — bot отвечает «No models installed»
- `query.answer()` вызывается до любой модификации — иначе Telegram показывает «идёт обработка» до таймаута

---

## Typing action

Перед LLM запросом вызывается `chat.send_action("typing")` — Telegram показывает индикатор «бот печатает». Актуально до получения ответа или ошибки (typing автоматически истекает через 5 секунд, не продлевается для длинных запросов — см. [discuss.md § 5](discuss.md#5-long-llm-requests--polling-timeout)).

---

## Gotchas

- **Разметка не используется** — все reply_text плоским текстом. Markdown / HTML не включён, поэтому LLM-ответы со специальными символами (`_`, `*`, `<`) показываются как есть.
- **Stale inline keyboard** — если пользователь вызвал `/models` несколько раз, старые сообщения с keyboard остаются интерактивными с устаревшим маркером. При тапе на старый keyboard — переключение всё равно работает, но визуальное состояние неконсистентно.
- **Длинные ответы LLM** — Telegram имеет лимит 4096 символов на сообщение. `reply_text` упадёт если LLM вернула больше. Сейчас не разбивается, это bug-в-ожидании (см. `legacy-warning.md` если добавите).
- **Нет progress-индикатора для долгих запросов** — typing шлётся один раз.
