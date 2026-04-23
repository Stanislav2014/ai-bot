# C-04 · Modular monolith — Users / Chat / History boundaries

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `C-04` |
| **Ticket** | — (homework refactor) |
| **Branch** | `feature/TD/C-04-modular-monolith` |
| **Task spec** | этот файл |
| **Started** | 2026-04-23 |
| **Status** | In Progress |
| **Owner** | Stan |

---

## Goal

Разнести логику бота на 4 изолированных модуля (`users/`, `chat/`, `history/`, `llm/`) с явными публичными API, чтобы транспорт (Telegram-handlers) не лез напрямую в LLM-клиент или хранилище истории — только через сервисный слой `chat/` и `users/`.

## Success criteria (verifiable)

- [ ] **CR-1**: `app/bot/handlers.py` импортит только `app.users` и `app.chat` (никаких `app.llm`, `app.history`) → verify: `grep -E '^from app\.(llm|history)' app/bot/handlers.py` пусто
- [ ] **CR-2**: `app/users/` — независимый модуль (нет импортов из `app.bot`, `app.chat`, `app.history`, `app.llm`) → verify: grep
- [ ] **CR-3**: `app/history/` и `app/llm/` не импортят друг друга и не импортят `app.users`, `app.chat`, `app.bot` → verify: grep
- [ ] **CR-4**: Persistent user state — выбор модели переживает рестарт. YAML per-user в `data/users/{telegram_id}.yaml` со схемой `{telegram_id, current_model, created_at}` → verify: integration test (`test_user_store.py`) + ручная проверка в Telegram
- [ ] **CR-5**: Все существующие user-facing flow работают идентично (handle_message, /models, /model, /reset, /start) → verify: набор юнит-тестов на `ChatService` + ручная проверка
- [ ] **CR-6**: `make test` зелёный (29 старых + новые), `make lint` чистый

---

## Scope

### In scope
- Новый модуль `app/users/` (UserStore + UserService + dataclass User)
- Новый модуль `app/chat/` (ChatService — оркестрация reply, list_models, reset_history)
- Рефакторинг `app/bot/handlers.py` — depends only on `users` + `chat`
- Перепрошивка DI в `app/main.py`
- Тесты: `tests/test_user_store.py`, `tests/test_user_service.py`, `tests/test_chat_service.py`
- Закрывает `D-03` из бэклога (persistent per-user model selection)
- Документация: `context-dump.md` обновлён по правилу из `instructions.md § 6`

### Out of scope
- Часть 2 ДЗ — придёт отдельной задачей
- Любая смена user-facing поведения (логи, тексты, формат истории — всё идентично)
- Streaming, rate-limiting, /stats, новый провайдер LLM
- Миграция существующих пользователей (на момент рефакторинга проде нет persistent user-state, поэтому миграция не нужна — все начинают с пустого `data/users/`)

---

## Impact / change surface

### Новые файлы
| Файл | Назначение |
|------|------------|
| `app/users/__init__.py` | Публичный re-export: `User`, `UserService` |
| `app/users/models.py` | `@dataclass User` (telegram_id, current_model, created_at) |
| `app/users/store.py` | `UserStore` — YAML per-user, `load`, `save`, `exists` |
| `app/users/service.py` | `UserService` — `get_or_create`, `get_model`, `set_model` |
| `app/chat/__init__.py` | Публичный re-export: `ChatService` |
| `app/chat/service.py` | `ChatService` — `reply`, `list_models`, `reset_history` |
| `tests/test_user_store.py` | YAML round-trip, isolation, corrupt recovery |
| `tests/test_user_service.py` | get_or_create, default fallback, set_model persistence |
| `tests/test_chat_service.py` | reply orchestration с моками llm/history/users/summarizer |

### Изменяемые файлы
| Файл | Характер |
|------|----------|
| `app/bot/handlers.py` | Удалить импорты `LLMClient`/`LLMError`/`HistoryStore`/`Summarizer`; зависимости — `UserService` + `ChatService`. `LLMError` обрабатывается внутри handler-а (re-export из `app.chat`). |
| `app/main.py` | Добавить wiring `UserStore → UserService`, `ChatService(...)`; собрать `BotHandlers(users, chat)` |
| `app/config.py` | Добавить `users_dir: str = "data/users"` |
| `.env.example` | Документировать `USERS_DIR` |
| `data/users/.gitkeep` | Каталог под persistent state |
| `docs/context-dump.md` | Карта модулей + Flow 2/4/5/6/8 → новые места ответственности; счётчик тестов |
| `docs/tasks.md` | Строка C-04 |
| `docs/sprints/current-sprint.md` | Открыть Sprint 2, добавить C-04 |
| `docs/change-request.md` | Блок C-04 |
| `docs/sprints/backlog.md` | Удалить D-03 (закрыто этой задачей) |

### Затронутые потоки
- **Flow 2** — `handle_message`: handler → `chat.reply(user_id, text)`. Вся оркестрация (history get/summarize/append, llm call, build messages с system_prompt) переезжает в `ChatService.reply`.
- **Flow 4** — `/models`: handler → `chat.list_models()` (фасад над `LLMClient.list_models`).
- **Flow 5** — inline keyboard: handler → `users.set_model(user_id, name)` + `chat.list_models()` для ререндера клавиатуры.
- **Flow 6** — `/model`: handler → `chat.list_models()` для валидации + `users.set_model`.
- **Flow 8** — `/reset`: handler → `chat.reset_history(user_id)`.

### Затронутые контракты
- Внешние контракты не меняются (Telegram, Lemonade — те же endpoint, формат)

---

## Architectural rules (matrix)

| Кто кого может звать | Разрешено | Запрещено |
|---|---|---|
| `bot/` → `users/`, `chat/` | да | прямо в `history/`, `llm/` |
| `chat/` → `users/`, `history/`, `llm/` | да | в `bot/` |
| `users/` ↔ `history/`, `llm/`, `chat/`, `bot/` | нет | вообще |
| `history/` ↔ `users/`, `chat/`, `bot/` | нет | вообще |
| `llm/` ↔ `users/`, `chat/`, `history/`, `bot/` | нет | вообще |

`users/`, `history/`, `llm/` зависят только от `app.config` и stdlib/3rd-party. `chat/` — единственный «склеивающий» слой; `bot/` — транспорт-адаптер.

---

## Public APIs

### `app.users`
```python
@dataclass
class User:
    telegram_id: int
    current_model: str | None
    created_at: str   # ISO

class UserStore:
    def __init__(self, data_dir: Path) -> None
    async def load(self, telegram_id: int) -> User | None
    async def save(self, user: User) -> None
    async def exists(self, telegram_id: int) -> bool

class UserService:
    def __init__(self, store: UserStore, default_model: str) -> None
    async def get_or_create(self, telegram_id: int) -> User
    async def get_model(self, telegram_id: int) -> str       # default_model fallback
    async def set_model(self, telegram_id: int, model: str) -> None
```

### `app.chat`
```python
class ChatService:
    def __init__(
        self,
        users: UserService,
        history: HistoryStore,
        summarizer: Summarizer,
        llm: LLMClient,
        system_prompt: str,
    ) -> None
    async def reply(self, telegram_id: int, text: str) -> str
    async def list_models(self) -> list[str]
    async def reset_history(self, telegram_id: int) -> None

# Re-export для удобства transport-слоя:
from app.llm.client import LLMError
```

### `app.bot.handlers` (после рефакторинга)
```python
class BotHandlers:
    def __init__(self, users: UserService, chat: ChatService) -> None
    # все методы на месте, телом дёргают только users + chat
```

---

## TDD phases

### Phase 0 — Research ✅
- Структура `app/` известна (см. § Impact)
- Паттерн YAML per-user — копируем из `app/history/store.py`
- pytest-asyncio mode=auto

### Phase 1 — Users module
- [ ] RED: `tests/test_user_store.py` — load empty, save+load roundtrip, per-user isolation, corrupt YAML recovery
- [ ] GREEN: `app/users/models.py`, `app/users/store.py`, `app/users/__init__.py`
- [ ] RED: `tests/test_user_service.py` — `get_or_create` создаёт + персистит, `get_model` fallback на default, `set_model` обновляет + персистит
- [ ] GREEN: `app/users/service.py`

### Phase 2 — Chat module
- [ ] RED: `tests/test_chat_service.py` — `reply` orchestration:
  - вызывает `users.get_model`
  - грузит `history.get`
  - вызывает `summarizer.maybe_summarize`, при изменении — `history.replace`
  - строит messages с system_prompt + history + user-msg
  - вызывает `llm.chat`
  - аппендит user + assistant в history
  - возвращает `result["content"]`
- [ ] RED: `list_models` → `llm.list_models`
- [ ] RED: `reset_history` → `history.reset`
- [ ] GREEN: `app/chat/service.py`, `app/chat/__init__.py`

### Phase 3 — Refactor transport
- [ ] Переписать `app/bot/handlers.py` под `users` + `chat`
- [ ] Перепрошить DI в `app/main.py`
- [ ] Обновить `app/config.py` (`users_dir`) + `.env.example`
- [ ] Создать `data/users/.gitkeep`

### Phase 4 — Verification
- [ ] `make test` — все тесты зелёные
- [ ] `make lint` — clean
- [ ] (manual) Telegram smoke — отложено до merge на проде, не блокер для In Review (нет тестового бота под рукой)

### Phase 5 — Docs
- [ ] `tasks.md` — C-04 ✅
- [ ] `current-sprint.md` — открыть Sprint 2, C-04 в Done после merge
- [ ] `change-request.md` — статус блока Merged
- [ ] `context-dump.md` — карта модулей + Flow + счётчик тестов
- [ ] `backlog.md` — удалить D-03

---

## Regression watch
- **`/models` после рестарта** — раньше выбор сбрасывался; теперь должен сохраняться. Smoke-проверка вручную.
- **History summarize → replace** — `ChatService.reply` должен идентично сохранять старое поведение (логи `history_summarized`, замена in-place).
- **Format логов** — все ключи (`user_id`, `model`, `username`, `text_length`, `reply_length`, `history_len`) — без изменений; иначе сломается прод-инспекция.

---

## History
- 2026-04-23 — started, спека + ветка `feature/TD/C-04-modular-monolith`
