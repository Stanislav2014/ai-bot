# Dialog examples — Sprint 1 acceptance artifacts

Скриншоты живых диалогов из Telegram, подтверждающих acceptance criteria Sprint 1 (см. [sprint-1-delivery.md](../sprint-1-delivery.md)).

## Файлы

### `stateless-vs-context-2026-04-17.png`

Одна сессия Telegram 2026-04-17 09:23–09:24. Модель `Qwen3-4B-Instruct-2507-GGUF`. Демонстрирует разницу в поведении бота **без контекста** (`HISTORY_ENABLED=false`) и **с контекстом** (`HISTORY_ENABLED=true`) — это ровно acceptance criterion «Показывать разницу в ответах при наличии и отсутствии контекста» из ТЗ спринта.

**Без контекста (stateless, `HISTORY_ENABLED=false`)**:
- `/reset` → «История диалога очищена.»
- `/models` → switch на `Qwen3-4B-Instruct-2507-GGUF`
- «Меня зовут Стас» → «Привет, Стас! Как могу помочь?»
- «Как меня зовут?» → **«Я не знаю, как тебя зовут. Меня зовут Тони.»** ← бот **забыл** предыдущее сообщение

**С контекстом (`HISTORY_ENABLED=true`)**:
- `/reset` → «История диалога очищена.»
- «Меня зовут Стас» → «Привет, Стас! Как могу помочь?»
- «Как меня зовут?» → **«Ты — Стас. 😊»** ← бот **помнит** предыдущее сообщение

Разница — **прямое следствие** D-10 флага `HISTORY_ENABLED`. В первом случае `HistoryStore.get()` возвращает `[]` и `append()` no-op; во втором — реальная история per-user загружается из YAML и подаётся в LLM как часть `messages`.

## Как воспроизвести

```bash
# 1. Stateless
echo "HISTORY_ENABLED=false" >> .env   # или поменяй существующую строку
make restart
# в Telegram: /reset, «Меня зовут X», «Как меня зовут?» → бот не помнит

# 2. С памятью
sed -i 's/^HISTORY_ENABLED=false/HISTORY_ENABLED=true/' .env
make restart
# в Telegram: /reset, «Меня зовут X», «Как меня зовут?» → бот помнит
```
