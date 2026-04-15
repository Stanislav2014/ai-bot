# D-04 · Dialog history — persistent YAML per-user

| Поле | Значение |
|------|----------|
| **Task ID** | D-04 |
| **Ticket** | BOT-D04 |
| **Branch** | `feature/BAU/BOT-D04` |
| **Status** | In Progress — Phase 0 (design approved, awaiting implementation plan) |
| **Owner** | Stan |
| **Started** | 2026-04-15 |

---

## Summary

Отход от stateless-архитектуры бота: хранить историю диалога в YAML-файлах (per-user), отправлять в LLM полную историю + новое сообщение, добавить `/reset`.

## Motivation

Сейчас каждое сообщение — изолированный LLM запрос. Пользователь не может задать follow-up. См. оригинальный вопрос в [discuss.md § 2](../discuss.md#2-dialog-history) — решение принято 2026-04-15 (variant B: persistent YAML).

---

## Design

### Архитектура

Новый модуль `app/history/` с одним публичным классом `HistoryStore`. Единственная ответственность: load/save list сообщений per user_id в YAML файл.

```
app/
├── history/
│   ├── __init__.py              — экспорт HistoryStore
│   └── store.py                 — HistoryStore class
├── bot/
│   └── handlers.py              — инъекция HistoryStore, изменения в handle_message, + reset handler
├── main.py                      — инстанцирование HistoryStore, регистрация /reset
└── config.py                    — новые env history_dir, history_max_messages
```

### HistoryStore API

```python
class HistoryStore:
    def __init__(self, data_dir: Path, max_messages: int) -> None: ...

    async def get(self, user_id: int) -> list[dict[str, str]]:
        """Вернуть историю пользователя. Пустой список если файла нет."""

    async def append(self, user_id: int, role: str, content: str) -> None:
        """Добавить сообщение, применить window trim, сохранить на диск."""

    async def reset(self, user_id: int) -> None:
        """Очистить историю пользователя (удалить файл и запись в кеше)."""
```

**In-memory cache** — `dict[int, list[dict]]` для скорости (избегает read на каждый запрос). Файл — source of truth при холодном старте / reset. На первый `get` для юзера: если в кеше нет — читаем файл.

**Concurrency** — `asyncio.Lock` per user (`dict[int, asyncio.Lock]`), чтобы конкурентные сообщения от одного юзера не гонялись за запись файла. Локи не чистим — при десятках активных пользователей утечка мизерная.

### Data shape

`data/history/{user_id}.yaml`:
```yaml
- role: user
  content: "Привет"
- role: assistant
  content: "Здравствуй!"
- role: user
  content: "Как дела?"
- role: assistant
  content: "Отлично, спасибо!"
```

**System prompt НЕ сохраняется в файле** — prepend-ится из кода (`SYSTEM_PROMPT` в `handlers.py`) при каждом LLM вызове. Причина: при изменении `SYSTEM_PROMPT` все пользователи сразу видят новую версию, без миграции файлов.

### Интеграция в handlers.py

**`BotHandlers.__init__`** — принимает `history: HistoryStore` дополнительно к `llm`.

**`handle_message` — новый flow**:
1. `history_msgs = await self.history.get(user_id)` — загрузить прошлые сообщения
2. `messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history_msgs + [{"role": "user", "content": text}]`
3. `result = await self.llm.chat(messages, model=model)`
4. `await self.history.append(user_id, "user", text)` — только после успешного LLM ответа
5. `await self.history.append(user_id, "assistant", result["content"])`
6. `reply_text(result["content"])`

**Важно**: append-ы **после** успешного LLM ответа. Если LLM упал — в историю ничего не попадает (не храним «зависшие» user сообщения без ответа, чтобы не ломать парность user/assistant в истории).

**Новая команда `reset`**:
```python
async def reset(self, update, context):
    user_id = update.effective_user.id
    await self.history.reset(user_id)
    logger.info("history_reset", user_id=user_id, username=update.effective_user.username)
    await update.message.reply_text("История диалога очищена.")
```

**`/start` и `/help`** — обновить текст: упомянуть `/reset`.

### Интеграция в main.py

```python
from app.history import HistoryStore
from pathlib import Path

history = HistoryStore(
    data_dir=Path(settings.history_dir),
    max_messages=settings.history_max_messages,
)
handlers = BotHandlers(llm=llm, history=history)
...
app.add_handler(CommandHandler("reset", handlers.reset))
```

### Config (app/config.py)

```python
history_dir: str = "data/history"
history_max_messages: int = 20   # 0 = unlimited
```

`.env.example` — добавить обе переменные с комментариями.

### Window logic

В `append()`:
```python
if self.max_messages > 0 and len(history) > self.max_messages:
    history = history[-self.max_messages:]
```

Чистый sliding по сообщениям (не по парам). Edge case: после обрезки первое сообщение может оказаться `assistant` — OpenAI-compatible серверы это принимают. Если окажется проблемой на практике — переделать на обрезку по парам (парность `user`+`assistant`).

### Error handling

| Ситуация | Поведение |
|----------|-----------|
| Файл не существует | `get()` возвращает `[]`, файл не создаётся до первого `append` |
| Файл есть, YAML невалидный | Лог `history_corrupt` (warning) + `get()` возвращает `[]` + файл перезаписывается пустым списком (рекавери) |
| Диск full / `PermissionError` при save | Лог `history_save_failed` (error) + прокинуть исключение вверх; в `handle_message` ловим отдельно, пользователю показываем generic error |
| `/reset` на несуществующий файл | No-op (не ошибка) |
| Concurrent `append` для одного юзера | Сериализуется per-user `asyncio.Lock` |

### Dockerfile / volumes

`Dockerfile` уже создаёт `/app/data` и даёт права `botuser`. `HistoryStore` создаст `history/` поддиректорию на старте.

⚠ **Regression watch**: `docker-compose.yml` сейчас **не** пробрасывает `data/` наружу контейнера. При `docker compose down` → `up` (но не `restart`) история теряется. Нужно добавить volume `- ./data:/app/data` в сервис `bot`. Это часть задачи.

---

## Success criteria (verifiable)

- [ ] Пользователь пишет 2 сообщения подряд — второе сообщение LLM получает с контекстом первого → verify: ручной тест в Telegram + лог `llm_request` содержит `messages_count > 2`
- [ ] При рестарте бота история сохраняется → verify: ручной тест (отправить сообщение → `docker compose restart bot` → продолжить диалог) + файл `data/history/{user_id}.yaml` существует и содержит прошлые сообщения
- [ ] При `docker compose down/up` история сохраняется → verify: volume проброшен, ручной тест
- [ ] Два разных пользователя видят только свою историю → verify: `test_per_user_isolation` + ручной тест с двумя аккаунтами
- [ ] Команда `/reset` очищает историю → verify: `test_reset_clears_file` + ручной тест
- [ ] Window лимит работает: `HISTORY_MAX_MESSAGES=4` → не больше 4 сообщений в файле → verify: `test_window_trims_when_over_limit`
- [ ] `HISTORY_MAX_MESSAGES=0` = без лимита → verify: `test_window_zero_means_unlimited`
- [ ] Corrupt YAML файл не ломает бота → verify: `test_corrupt_yaml_recovers`
- [ ] `make test` зелёный · `make lint` зелёный

---

## Scope

### In scope
- Новый модуль `app/history/` (`__init__.py`, `store.py`)
- Интеграция в `BotHandlers.handle_message`
- Новая команда `/reset`
- Env `HISTORY_DIR`, `HISTORY_MAX_MESSAGES`
- Зависимость `PyYAML==6.0.2`
- Тесты `tests/test_history_store.py` (8 тестов)
- `docker-compose.yml` — volume для `data/`
- `.env.example` — новые переменные
- `/start` и `/help` тексты — упомянуть `/reset`
- Обновление docs (см. ниже)

### Out of scope
- Отдельное сохранение system prompt в файле (всегда prepend из кода)
- Persistent `user_models` dict — отдельная задача D-03
- Миграция existing пользователей (их нет)
- Compression/archival старых историй
- Команды просмотра/частичного редактирования истории
- История для медиа / вложений (у бота сейчас только текст)

---

## Impact / change surface

### Изменяемые файлы
| Файл | Характер изменений |
|------|--------------------|
| `app/history/__init__.py` | **NEW** — экспорт `HistoryStore` |
| `app/history/store.py` | **NEW** — `HistoryStore` класс |
| `app/bot/handlers.py` | Инъекция `history` в `__init__`, изменения в `handle_message`, новый `reset` хэндлер, обновление текстов |
| `app/main.py` | Инстанцирование `HistoryStore`, передача в `BotHandlers`, регистрация `CommandHandler("reset")` |
| `app/config.py` | Добавить `history_dir`, `history_max_messages` |
| `requirements.txt` | + `PyYAML==6.0.2` |
| `.env.example` | + `HISTORY_DIR`, `HISTORY_MAX_MESSAGES` |
| `docker-compose.yml` | + volume `./data:/app/data` для сервиса `bot` |
| `tests/test_history_store.py` | **NEW** — 8 тестов |

### Затронутые потоки (из [context-dump.md](../context-dump.md))
- **Flow 2 — Incoming text message (happy path)**: добавляются шаги load history перед LLM + append после ответа
- **Flow 7 — `/start`/`/help`**: обновить текст помощи
- **Новый Flow 9 — `/reset`**: полностью новый

### Затронутые контракты
- **contracts/external/ollama.md** — `messages` массив теперь `[system] + history + [user]`. Риск: context-length exceeded на длинных историях — смягчается window limit.

---

## Uncertainty list

1. **Window FIFO по сообщениям или по парам?** Решение: по сообщениям (проще). После обрезки первое сообщение может оказаться `assistant`. Если ухудшит качество — переделать на обрезку по парам.
2. **PyYAML performance** — `yaml.safe_load`/`yaml.safe_dump` sync внутри async метода. Файлы маленькие (<5KB), займёт <1ms. Если профайлер покажет блокировки — обернуть в `asyncio.to_thread`.
3. **`user_id` как имя файла** — `int` → `f"{user_id}.yaml"`. Telegram user_id это int64, безопасно (нет `/` или других спецсимволов).
4. **Локи per user — очищать ли?** Не чистим. Утечка мизерная (размер dict = число когда-либо активных юзеров).
5. **История при LLM ошибке** — решено **не** сохранять user сообщение если LLM упал. Иначе сломается парность user/assistant и следующий запрос выглядит странно для модели.

---

## Test plan

`tests/test_history_store.py`:
1. `test_get_empty_user` — нет файла, `get()` → `[]`
2. `test_append_and_get` — пара user+assistant, правильный порядок
3. `test_persistence_across_instances` — новый `HistoryStore` с тем же dir читает что написал старый
4. `test_window_trims_when_over_limit` — `max_messages=4`, append 6 → длина 4
5. `test_window_zero_means_unlimited` — `max_messages=0`, append 50 → длина 50
6. `test_reset_clears_file` — append → reset → `get()` → `[]` + файла нет
7. `test_corrupt_yaml_recovers` — подложить битый yaml, `get()` → `[]`, файл восстановлен
8. `test_per_user_isolation` — два разных `user_id`, append разное, проверка изоляции

**Handlers integration** — без формального unit-теста (BotHandlers не покрыт тестами вообще, см. [testing.md](../testing.md)). Покрытие ручное:
- Запустить бота, отправить 2 сообщения, проверить что второе понимает контекст
- Рестарт бота → история сохранилась
- `docker compose down` → `up` → история сохранилась (volume)
- `/reset` → история очищена, файл удалён
- Второй пользователь (другой аккаунт) не видит историю первого
- `make test` зелёный
- `make lint` зелёный

---

## TDD phases

### Phase 0 — Research / Design
- [x] Brainstorming, variant B выбран
- [x] Полный дизайн записан (этот файл)
- [ ] Implementation plan создан через writing-plans skill

### Phase 1 — HistoryStore (TDD)
- [ ] RED → GREEN → REFACTOR для каждого теста из Test plan (8 циклов)

### Phase 2 — Config
- [ ] `app/config.py` — новые поля
- [ ] `.env.example` — новые переменные

### Phase 3 — Handlers
- [ ] Инъекция `history` в `BotHandlers.__init__`
- [ ] `handle_message` — load → build messages → LLM → append user → append assistant
- [ ] `reset` handler
- [ ] Обновить тексты `/start` и `/help`

### Phase 4 — Wiring в main.py
- [ ] Инстанцировать `HistoryStore`
- [ ] Передать в `BotHandlers`
- [ ] `CommandHandler("reset")` зарегистрирован

### Phase 5 — Infrastructure
- [ ] `requirements.txt` — `PyYAML==6.0.2`
- [ ] `docker-compose.yml` — volume `./data:/app/data`
- [ ] Локальная проверка `make build` + `make up`

### Phase 6 — Manual testing
- [ ] 2 сообщения подряд — контекст виден
- [ ] Рестарт бота — история жива
- [ ] `docker compose down/up` — история жива
- [ ] `/reset` — очищено
- [ ] Два аккаунта — изоляция
- [ ] `make test` зелёный
- [ ] `make lint` зелёный

### Phase 7 — Docs update
- [ ] `context-dump.md` Flow 2 — новые шаги load/append
- [ ] `context-dump.md` — новый Flow 9: `/reset`
- [ ] `discuss.md § 2` — решение зафиксировано
- [ ] `legacy-warning.md § 4` — сузить scope до `user_models` (история теперь персистентна)
- [ ] `db-schema.md` — YAML files per user в «Что где хранится»
- [ ] `architecture.md` — паттерн «Per-user persistent history» + edge case concurrent writes
- [ ] `ui-kit.md` — команда `/reset` + тексты
- [ ] `tech-stack.md` — `PyYAML==6.0.2`
- [ ] `tasks.md` — D-04 → ✅
- [ ] `current-sprint.md` — D-04 → Done

---

## Regression watch

- **Flow 2 изменён** — risk сломать single-message поведение. `tests/test_llm_client.py` должны остаться зелёными (LLMClient не трогаем).
- **LLM context length** — длинные истории могут превысить context window модели. Window limit (20 по дефолту) смягчает, но не полностью. Риск: 400 от Lemonade на редких длинных диалогах.
- **`data/` volume в docker-compose** — **обязательно** добавить, иначе `down/up` теряет историю.
- **Dockerfile perms** — `history/` создаётся под `botuser`, должно работать (у botuser права на `/app/data`).
- **Stale `_locks` dict** — минимальная утечка при очень большом числе разных юзеров (in practice никогда не проявится для self-hosted бота).

---

## Dependencies

- `PyYAML==6.0.2` — новая runtime зависимость (MIT license, stable, широко используется)

---

## Links

- [change-request.md](../change-request.md) — live TDD tracker
- [discuss.md § 2](../discuss.md#2-dialog-history) — исходная мотивация
- [architecture.md](../architecture.md) — будет обновлён в Phase 7
- [context-dump.md](../context-dump.md) — будет обновлён в Phase 7
- [contracts/external/ollama.md](../contracts/external/ollama.md) — messages array меняется

---

## History

- 2026-04-15 — task started; brainstorming завершён (variant B: persistent YAML); design утверждён; spec записан в этот файл
