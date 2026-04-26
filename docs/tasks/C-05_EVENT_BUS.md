# C-05 · In-memory event bus — decouple Chat ↔ History via events

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `C-05` |
| **Ticket** | — (homework refactor, Часть 2) |
| **Branch** | `feature/TD/C-05-event-bus` |
| **Task spec** | этот файл |
| **Started** | 2026-04-25 |
| **Status** | In Review |
| **Owner** | Stan |

---

## Goal

Внедрить простой in-memory event bus и развязать `chat/` и `history/`: `chat/` больше не дёргает `history.append/replace` напрямую — публикует события `MessageReceived` / `ResponseGenerated` / `HistorySummarized`, а `history/` подписывается и сохраняет. Дополнительно — `users/` публикует `UserCreated` при первом обращении.

## Success criteria (verifiable)

- [x] **CR-1**: `app/chat/` НЕ импортит `app.history` → verified grep clean
- [x] **CR-2**: `app/history/` НЕ импортит `app.chat`, `app.users`, `app.bot`, `app.llm` → verified grep clean
- [x] **CR-3**: `app/events/` zero app-deps → verified grep clean (только intra-module + stdlib)
- [x] **CR-4**: `ChatService.reply` публикует `MessageReceived` (user) + `ResponseGenerated` (assistant); при summarize → `HistorySummarized`; reset → `HistoryResetRequested`. Без LLM-ошибки → не публикует. Verified в `test_chat_service.py` (11 тестов)
- [x] **CR-5**: `UserService.get_or_create` публикует `UserCreated` только для нового пользователя. Verified в `test_user_service.py` (3 новых теста)
- [x] **CR-6**: History subscriber: 4 события → правильные методы store + per-user isolation. Verified в `test_history_subscriber.py` (6 тестов)
- [x] **CR-7**: User-facing flow идентичен (sequential publish сохраняет порядок записи; логи `llm_reply`/`history_summarized` те же). DI smoke без сети подтверждает что события доходят и история пишется
- [x] **CR-8**: `make test` 69/69 ✅, `make lint` clean ✅

---

## Scope

### In scope
- Новый модуль `app/events/` (EventBus + event dataclasses)
- Рефакторинг `ChatService.reply` — публикует события, убран `history.append/replace`
- Рефакторинг `ChatService` — принимает не `HistoryStore`, а свой Protocol `HistoryReader` (read-only для сборки контекста)
- Рефакторинг `UserService.get_or_create` — принимает `EventBus`, публикует `UserCreated` при создании
- Новый файл `app/history/subscriber.py` — функция `subscribe(bus, store)` регистрирует обработчики
- Тесты: `tests/test_event_bus.py`, `tests/test_history_subscriber.py`, обновление `test_chat_service.py` и `test_user_service.py`
- Wiring в `app/main.py`
- Документация: `context-dump.md`, `change-request.md`, `current-sprint.md`, `tasks.md`

### Out of scope
- Persistence событий, retry, dead-letter queue
- Любая внешняя очередь (Kafka, RabbitMQ)
- Конкурентный fan-out (subscriber'ы запускаются последовательно — детерминизм важнее)
- Часть 3+ ДЗ
- Изменение user-facing поведения

---

## Impact / change surface

### Новые файлы
| Файл | Назначение |
|------|------------|
| `app/events/__init__.py` | Re-export: `EventBus`, `UserCreated`, `MessageReceived`, `ResponseGenerated`, `HistorySummarized` |
| `app/events/bus.py` | `EventBus` — `subscribe(event_type, handler)`, `publish(event)` (sequential await) |
| `app/events/types.py` | Frozen dataclasses событий |
| `app/history/subscriber.py` | `subscribe(bus, store)` — регистрирует handlers под 3 события |
| `tests/test_event_bus.py` | Unit-тесты EventBus |
| `tests/test_history_subscriber.py` | Интеграция bus + HistoryStore |

### Изменяемые файлы
| Файл | Характер |
|------|----------|
| `app/chat/service.py` | Убрать импорт `app.history`; ввести Protocol `HistoryReader`; `reply` публикует события вместо `history.append/replace`; принимает `EventBus` |
| `app/users/service.py` | `__init__` принимает `EventBus`; `get_or_create` публикует `UserCreated` при создании |
| `app/main.py` | Создать `EventBus`, передать в `UserService`, `ChatService`; вызвать `history.subscriber.subscribe(bus, history)` |
| `tests/test_chat_service.py` | Обновить fixtures (EventBus); проверять публикацию событий вместо `history.get(...)` |
| `tests/test_user_service.py` | Обновить fixtures (EventBus); добавить тесты на публикацию `UserCreated` |
| `docs/context-dump.md` | Карта модулей: `events/`; обновить Flow 1/2/8 (event-driven путь) |
| `docs/tasks.md` | Строка C-05 |
| `docs/sprints/current-sprint.md` | C-05: To Do → In Progress → In Review |
| `docs/change-request.md` | Блок C-05 |

### Затронутые потоки
- **Flow 1** — `/start`: `users.get_or_create` теперь публикует `UserCreated` (если новый). Подписчиков пока нет — эвент уходит «в пустоту», но контракт зафиксирован для будущих обработчиков (analytics, welcome message и т.п.)
- **Flow 2** — `handle_message`: `chat.reply` → `bus.publish(MessageReceived)` → history subscriber пишет; `bus.publish(ResponseGenerated)` → пишет ответ. Summarize → `bus.publish(HistorySummarized)` → history.replace
- **Flow 8** — `/reset`: остаётся прямым вызовом `chat.reset_history` → `history.reset`. Это команда, не событие — синхронный ответ нужен пользователю

### Затронутые контракты
- Внешние не меняются (Telegram, Lemonade — те же endpoint, формат)
- Внутренние: `ChatService.__init__` сигнатура +`bus`, -`history` (now `HistoryReader` Protocol). `UserService.__init__` сигнатура +`bus`

---

## Architectural rules (matrix, обновлено)

| Кто кого может звать | Разрешено | Запрещено |
|---|---|---|
| `bot/` → `users/`, `chat/` | да | прямо в `history/`, `llm/`, `events/` |
| `chat/` → `users/`, `llm/`, `events/` | да | прямо в `history/`, `bot/` |
| `users/` → `events/` | да | в `history/`, `chat/`, `llm/`, `bot/` |
| `history/` → `events/` | да | в `users/`, `chat/`, `bot/`, `llm/` |
| `llm/` → ∅ | — | вообще ни во что |
| `events/` → ∅ | — | вообще ни во что |

`events/` — новый foundational слой (как `config/`). Может зависеть только от stdlib.

---

## Public APIs

### `app.events`
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class UserCreated:
    telegram_id: int
    created_at: str

@dataclass(frozen=True)
class MessageReceived:
    telegram_id: int
    text: str

@dataclass(frozen=True)
class ResponseGenerated:
    telegram_id: int
    text: str

@dataclass(frozen=True)
class HistorySummarized:
    telegram_id: int
    messages: list[dict[str, str]]

class EventBus:
    def subscribe(self, event_type: type, handler: Callable[[Any], Awaitable[None]]) -> None
    async def publish(self, event: Any) -> None  # sequential, propagates errors
```

### `app.chat` (обновлено)
```python
class HistoryReader(Protocol):
    async def get(self, telegram_id: int) -> list[dict[str, str]]: ...

class ChatService:
    def __init__(
        self,
        users: UserService,
        history: HistoryReader,
        summarizer: Summarizer,
        llm: LLMClient,
        bus: EventBus,
        system_prompt: str,
    ) -> None
    async def reply(self, telegram_id: int, text: str) -> str
    async def list_models(self) -> list[str]
    async def reset_history(self, telegram_id: int) -> None  # delegated to a separate read-write port (or: removed in favor of an event later)
```

> Решение по ходу: `reset_history` пока оставляем прямым (Flow 8 требует подтверждения пользователю — синхронный путь). Если уйдём на чисто event-driven, понадобится request/reply механизм — за пределами Часть 2.

### `app.users` (обновлено)
```python
class UserService:
    def __init__(
        self,
        store: UserStore,
        default_model: str,
        bus: EventBus,
    ) -> None
    async def get_or_create(self, telegram_id: int) -> User       # publishes UserCreated if new
    async def get_model(self, telegram_id: int) -> str
    async def set_model(self, telegram_id: int, model: str) -> None
```

### `app.history.subscriber`
```python
def subscribe(bus: EventBus, store: HistoryStore) -> None
    # registers 3 handlers:
    # - MessageReceived → store.append(user_id, "user", text)
    # - ResponseGenerated → store.append(user_id, "assistant", text)
    # - HistorySummarized → store.replace(user_id, messages)
```

---

## TDD phases

### Phase 1 — EventBus
- [ ] RED: `tests/test_event_bus.py`
  - subscribe + publish: handler вызван с event
  - 2 subscriber'а на один тип: оба вызваны в порядке регистрации
  - publish без subscriber'ов: не падает
  - publish event типа A: handler типа B не вызван
  - subscriber падает: исключение пробрасывается
  - async handler: правильно awaited
- [ ] GREEN: `app/events/bus.py`, `app/events/types.py`, `app/events/__init__.py`

### Phase 2 — UserService publishes UserCreated
- [ ] RED: обновить `tests/test_user_service.py`
  - fixture `bus`, fixture обновлённого service с `bus`
  - `get_or_create(new)` → событие `UserCreated(telegram_id, created_at)` поймано подписчиком
  - `get_or_create(existing)` → событий нет
- [ ] GREEN: `app/users/service.py` — добавить `bus` в `__init__`, publish в `get_or_create`

### Phase 3 — ChatService → events
- [ ] RED: обновить `tests/test_chat_service.py`
  - fixture `bus`, fixture обновлённого `ChatService` с `bus` и `HistoryReader`
  - `reply` публикует `MessageReceived(user_id, "hi")` потом `ResponseGenerated(user_id, "hello reply")` (порядок!)
  - `reply` НЕ вызывает `history.append` (мокаем reader, проверяем что `append` не существует / не дёргается через spy)
  - При summarize → `HistorySummarized(user_id, new_messages)` опубликовано перед `MessageReceived`
  - LLMError → не публикуется ни `MessageReceived`, ни `ResponseGenerated` (заранее ничего, потом ошибка). История не задета
- [ ] GREEN: `app/chat/service.py` — убрать `app.history` импорт, ввести `HistoryReader` Protocol, поменять writes на `bus.publish`

### Phase 4 — History subscriber
- [ ] RED: `tests/test_history_subscriber.py`
  - `subscribe(bus, store)` зарегистрировал 3 handler'а
  - Publish `MessageReceived(1, "hi")` → `await store.get(1) == [{"user": "hi"}]`
  - Publish `ResponseGenerated(1, "ans")` → история имеет assistant
  - Publish `HistorySummarized(1, [...])` → история заменена
- [ ] GREEN: `app/history/subscriber.py`

### Phase 5 — Wire in main.py
- [ ] Создать `EventBus`, передать в `UserService`, `ChatService`
- [ ] Вызвать `app.history.subscriber.subscribe(bus, history)`
- [ ] DI smoke: `python -c "from app.main import run; ..."` без сети

### Phase 6 — Verify
- [ ] `make test` — все зелёные (52 + новые)
- [ ] `make lint` — clean
- [ ] grep: `app/chat/` без `app.history`, `app/events/` без `app.*`
- [ ] (manual) Telegram smoke — отложен до merge

### Phase 7 — Docs
- [ ] `tasks.md` — C-05
- [ ] `current-sprint.md` — In Progress → In Review
- [ ] `change-request.md` — блок C-05
- [ ] `context-dump.md` — модуль `events/`, обновить Flow 1/2

---

## Regression watch
- **Format логов** — `llm_reply`, `history_summarized` — те же ключи; иначе сломается прод-инспекция
- **Порядок записи в историю** — раньше: append(user) → append(assistant). Теперь: publish(MessageReceived) → publish(ResponseGenerated). Поскольку bus sequential — порядок сохранится
- **Persistence истории** — теперь зависит от того, что history-subscriber успешно отработал. Если subscriber упадёт — `publish` пробросит, ChatService.reply упадёт. Это OK — лучше упасть громко, чем тихо потерять сообщение

---

## History
- 2026-04-25 — started, спека + ветка `feature/TD/C-05-event-bus`
- 2026-04-25 — Phase 1 (EventBus): `tests/test_event_bus.py` (6) GREEN; `app/events/{bus,types,__init__}.py` созданы
- 2026-04-25 — Phase 2 (UserService): 3 новых теста на публикацию `UserCreated` GREEN; `UserService.__init__` теперь принимает `bus`
- 2026-04-25 — Phase 3 (ChatService): полная переделка `test_chat_service.py` (11 тестов, включая failure path и порядок событий) GREEN; `ChatService` больше не импортит `app.history`, `HistoryReader` Protocol для read-only. **Решение по ходу**: добавлено 5-е событие `HistoryResetRequested` — `reset_history` тоже идёт через bus, иначе chat дёргал бы `history.reset` напрямую
- 2026-04-25 — Phase 4 (History subscriber): `tests/test_history_subscriber.py` (6) GREEN; `app/history/subscriber.py` с handler-ами под 4 события
- 2026-04-25 — Phase 5 (Wire): `EventBus` в `main.py`, `subscribe_history(bus, history)`, передан в `UserService` и `ChatService`. DI smoke без сети — события прокидываются, история пишется
- 2026-04-25 — Phase 6 (Verify): 69/69 tests green, ruff clean, grep подтвердил все 6 архитектурных правил
- 2026-04-25 — Phase 7 (Docs): context-dump (карта модулей + Flow 1/2/7/8 + счётчик 52→69); tasks.md C-05; change-request → In Review; current-sprint C-05 → In Review
- 2026-04-25 — In Review: ждёт ручной Telegram-smoke от Stan (после merge C-04 → master → rebase C-05) и merge
