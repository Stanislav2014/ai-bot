# D-04 Dialog History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить персистентную per-user историю диалога в YAML, интегрировать в message flow, добавить `/reset`.

**Architecture:** Новый модуль `app/history/store.py` с классом `HistoryStore` (YAML файлы под `data/history/{user_id}.yaml`, in-memory cache, per-user `asyncio.Lock`, sliding window). Интеграция в `BotHandlers.handle_message` и новая команда `/reset`. Volume для `data/` в docker-compose.

**Tech Stack:** Python 3.11+, PyYAML, pytest-asyncio (`asyncio_mode=auto`), structlog.

**Full spec:** [D-04_DIALOG_HISTORY_YAML.md](D-04_DIALOG_HISTORY_YAML.md)

---

## File structure

```
app/
├── history/
│   ├── __init__.py              NEW · экспорт HistoryStore
│   └── store.py                 NEW · HistoryStore class
├── bot/
│   └── handlers.py              MODIFY · инъекция history, новый handle_message, новый reset
├── main.py                      MODIFY · инстанцирование + регистрация /reset
└── config.py                    MODIFY · +history_dir +history_max_messages

tests/
└── test_history_store.py        NEW · 8 тестов

requirements.txt                 MODIFY · +PyYAML
.env.example                     MODIFY · +HISTORY_DIR +HISTORY_MAX_MESSAGES
docker-compose.yml               MODIFY · +volume data/
```

---

## Task 1: Добавить PyYAML зависимость

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Добавить строку**

Обновить `requirements.txt`:
```
python-telegram-bot==21.9
httpx==0.28.1
pydantic-settings==2.7.1
structlog==24.4.0
PyYAML==6.0.2
```

- [ ] **Step 2: Установить локально для тестов**

Run: `pip install PyYAML==6.0.2`
Expected: `Successfully installed PyYAML-6.0.2`

- [ ] **Step 3: Коммит**

```bash
git add requirements.txt
git commit -m "feat(D-04): add PyYAML dependency for dialog history"
```

---

## Task 2: HistoryStore — тест get() на пустом юзере (RED → GREEN)

**Files:**
- Create: `app/history/__init__.py`
- Create: `app/history/store.py`
- Create: `tests/test_history_store.py`

- [ ] **Step 1: Создать `app/history/__init__.py`**

```python
from app.history.store import HistoryStore

__all__ = ["HistoryStore"]
```

- [ ] **Step 2: Написать падающий тест**

Создать `tests/test_history_store.py`:
```python
from pathlib import Path

import pytest

from app.history import HistoryStore


@pytest.fixture
def history_dir(tmp_path: Path) -> Path:
    return tmp_path / "history"


async def test_get_empty_user(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    assert await store.get(1) == []
```

- [ ] **Step 3: Запустить — должен упасть на import**

Run: `python3 -m pytest tests/test_history_store.py::test_get_empty_user -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.history.store'` или `ImportError`.

- [ ] **Step 4: Создать минимальный `app/history/store.py`**

```python
import asyncio
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()


class HistoryStore:
    def __init__(self, data_dir: Path, max_messages: int) -> None:
        self._data_dir = data_dir
        self._max_messages = max_messages
        self._cache: dict[int, list[dict[str, str]]] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def _file(self, user_id: int) -> Path:
        return self._data_dir / f"{user_id}.yaml"

    def _load_from_disk(self, user_id: int) -> list[dict[str, str]]:
        path = self._file(user_id)
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                raise ValueError("history file must contain a list")
            return data
        except (yaml.YAMLError, ValueError) as e:
            logger.warning("history_corrupt", user_id=user_id, error=str(e))
            path.write_text("[]\n", encoding="utf-8")
            return []

    async def get(self, user_id: int) -> list[dict[str, str]]:
        async with self._lock(user_id):
            if user_id not in self._cache:
                self._cache[user_id] = self._load_from_disk(user_id)
            return list(self._cache[user_id])
```

- [ ] **Step 5: Прогнать тест — должен пройти**

Run: `python3 -m pytest tests/test_history_store.py::test_get_empty_user -v`
Expected: PASS.

- [ ] **Step 6: Коммит**

```bash
git add app/history/ tests/test_history_store.py
git commit -m "feat(D-04): HistoryStore skeleton with get() for empty user"
```

---

## Task 3: HistoryStore — append + get (RED → GREEN)

**Files:**
- Modify: `tests/test_history_store.py`
- Modify: `app/history/store.py`

- [ ] **Step 1: Добавить падающий тест**

В `tests/test_history_store.py`:
```python
async def test_append_and_get(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "hi")
    await store.append(1, "assistant", "hello")
    assert await store.get(1) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
```

- [ ] **Step 2: Запустить — должен упасть (нет `append`)**

Run: `python3 -m pytest tests/test_history_store.py::test_append_and_get -v`
Expected: FAIL — `AttributeError: 'HistoryStore' object has no attribute 'append'`.

- [ ] **Step 3: Реализовать `append`**

Добавить в `app/history/store.py` в `HistoryStore`:
```python
    async def append(self, user_id: int, role: str, content: str) -> None:
        async with self._lock(user_id):
            if user_id not in self._cache:
                self._cache[user_id] = self._load_from_disk(user_id)
            history = self._cache[user_id]
            history.append({"role": role, "content": content})
            if self._max_messages > 0 and len(history) > self._max_messages:
                history = history[-self._max_messages:]
                self._cache[user_id] = history
            with self._file(user_id).open("w", encoding="utf-8") as f:
                yaml.safe_dump(history, f, allow_unicode=True, sort_keys=False)
```

- [ ] **Step 4: Прогнать — зелёный**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: обе функции PASS.

- [ ] **Step 5: Коммит**

```bash
git add app/history/store.py tests/test_history_store.py
git commit -m "feat(D-04): HistoryStore.append with YAML persist"
```

---

## Task 4: HistoryStore — persistence across instances

**Files:**
- Modify: `tests/test_history_store.py`

- [ ] **Step 1: Добавить тест**

```python
async def test_persistence_across_instances(history_dir: Path) -> None:
    s1 = HistoryStore(history_dir, max_messages=20)
    await s1.append(1, "user", "persistent")
    s2 = HistoryStore(history_dir, max_messages=20)
    assert await s2.get(1) == [{"role": "user", "content": "persistent"}]
```

- [ ] **Step 2: Прогнать**

Run: `python3 -m pytest tests/test_history_store.py::test_persistence_across_instances -v`
Expected: PASS (реализация уже это поддерживает — файл на диске + `_load_from_disk` в `get`).

- [ ] **Step 3: Коммит**

```bash
git add tests/test_history_store.py
git commit -m "test(D-04): verify HistoryStore persistence across instances"
```

---

## Task 5: HistoryStore — window trim

**Files:**
- Modify: `tests/test_history_store.py`

- [ ] **Step 1: Добавить два теста**

```python
async def test_window_trims_when_over_limit(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=4)
    for i in range(6):
        await store.append(1, "user", f"m{i}")
    result = await store.get(1)
    assert len(result) == 4
    assert result[0]["content"] == "m2"
    assert result[-1]["content"] == "m5"


async def test_window_zero_means_unlimited(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=0)
    for i in range(50):
        await store.append(1, "user", f"m{i}")
    assert len(await store.get(1)) == 50
```

- [ ] **Step 2: Прогнать**

Run: `python3 -m pytest tests/test_history_store.py -v -k window`
Expected: оба PASS (логика уже в append).

- [ ] **Step 3: Коммит**

```bash
git add tests/test_history_store.py
git commit -m "test(D-04): HistoryStore sliding window limit + unlimited"
```

---

## Task 6: HistoryStore — reset (RED → GREEN)

**Files:**
- Modify: `tests/test_history_store.py`
- Modify: `app/history/store.py`

- [ ] **Step 1: Падающий тест**

```python
async def test_reset_clears_file(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "hi")
    await store.reset(1)
    assert await store.get(1) == []
    assert not (history_dir / "1.yaml").exists()
```

- [ ] **Step 2: Прогнать — упадёт**

Run: `python3 -m pytest tests/test_history_store.py::test_reset_clears_file -v`
Expected: FAIL — `AttributeError: ... reset`.

- [ ] **Step 3: Реализовать `reset`**

Добавить в `HistoryStore`:
```python
    async def reset(self, user_id: int) -> None:
        async with self._lock(user_id):
            self._cache.pop(user_id, None)
            path = self._file(user_id)
            if path.exists():
                path.unlink()
```

- [ ] **Step 4: Прогнать — зелёный**

Run: `python3 -m pytest tests/test_history_store.py::test_reset_clears_file -v`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add app/history/store.py tests/test_history_store.py
git commit -m "feat(D-04): HistoryStore.reset clears cache and file"
```

---

## Task 7: HistoryStore — corrupt recovery + isolation

**Files:**
- Modify: `tests/test_history_store.py`

- [ ] **Step 1: Добавить два теста**

```python
async def test_corrupt_yaml_recovers(history_dir: Path) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "1.yaml").write_text("!!!garbage:::\n- [}\n", encoding="utf-8")
    store = HistoryStore(history_dir, max_messages=20)
    assert await store.get(1) == []


async def test_per_user_isolation(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "from 1")
    await store.append(2, "user", "from 2")
    assert await store.get(1) == [{"role": "user", "content": "from 1"}]
    assert await store.get(2) == [{"role": "user", "content": "from 2"}]
```

- [ ] **Step 2: Прогнать**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: все 8 тестов PASS.

- [ ] **Step 3: Линт**

Run: `python3 -m ruff check app/history tests/test_history_store.py`
Expected: `All checks passed!`.

- [ ] **Step 4: Коммит**

```bash
git add tests/test_history_store.py
git commit -m "test(D-04): HistoryStore corrupt recovery and per-user isolation"
```

---

## Task 8: Config + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Обновить `app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    llm_base_url: str = "http://ollama:11434"
    default_model: str = "qwen3:0.6b"
    llm_timeout: int = 120
    log_level: str = "INFO"
    history_dir: str = "data/history"
    history_max_messages: int = 20

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 2: Обновить `.env.example`**

```
# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=

# LLM server base URL (Ollama, Lemonade, vLLM, etc.)
LLM_BASE_URL=http://lemonade:8000/api

# Default LLM model
DEFAULT_MODEL=Qwen3-0.6B-GGUF

# LLM request timeout in seconds
LLM_TIMEOUT=120

# Logging level
LOG_LEVEL=INFO

# Dialog history directory (per-user YAML files)
HISTORY_DIR=data/history

# Max messages kept per user (0 = unlimited)
HISTORY_MAX_MESSAGES=20
```

- [ ] **Step 3: Прогнать существующие тесты (config не должен ничего ломать)**

Run: `python3 -m pytest tests/ -v`
Expected: всё зелёное.

- [ ] **Step 4: Коммит**

```bash
git add app/config.py .env.example
git commit -m "feat(D-04): config history_dir and history_max_messages"
```

---

## Task 9: Integrate HistoryStore в handlers.py

**Files:**
- Modify: `app/bot/handlers.py`

- [ ] **Step 1: Обновить импорты и `__init__`**

Заменить в начале `app/bot/handlers.py` блок импортов + класс `BotHandlers.__init__`:
```python
import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.history import HistoryStore
from app.llm.client import LLMClient, LLMError

logger = structlog.get_logger()

SYSTEM_PROMPT = "You are a helpful assistant. Answer concisely and accurately."


class BotHandlers:
    def __init__(self, llm: LLMClient, history: HistoryStore) -> None:
        self.llm = llm
        self.history = history
        self.user_models: dict[int, str] = {}
```

- [ ] **Step 2: Заменить `handle_message`**

Полная замена метода `handle_message`:
```python
    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        user_id = user.id
        text = update.message.text
        model = self._get_model(user_id)

        logger.info(
            "user_message",
            user_id=user_id,
            username=user.username,
            model=model,
            text_length=len(text),
        )

        history_msgs = await self.history.get(user_id)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history_msgs
            + [{"role": "user", "content": text}]
        )

        try:
            await update.message.chat.send_action("typing")
            result = await self.llm.chat(messages, model=model)
            reply = result["content"]

            await self.history.append(user_id, "user", text)
            await self.history.append(user_id, "assistant", reply)

            logger.info(
                "llm_reply",
                user_id=user_id,
                model=model,
                reply_length=len(reply),
                history_len=len(history_msgs) + 2,
            )
            await update.message.reply_text(reply)

        except LLMError as e:
            logger.error("llm_error", user_id=user_id, error=str(e))
            if "404" in str(e):
                await update.message.reply_text(
                    f"Model '{model}' is not available. Use /models to see installed models."
                )
            else:
                await update.message.reply_text(
                    "Sorry, the language model is currently unavailable. Please try again later."
                )
        except Exception:
            logger.exception("unexpected_error", user_id=user_id)
            await update.message.reply_text(
                "An unexpected error occurred. Please try again later."
            )
```

- [ ] **Step 3: Обновить `start` — упомянуть `/reset`**

Заменить тело `start` метода:
```python
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info("command_start", user_id=user.id, username=user.username)
        await update.message.reply_text(
            f"Hello, {user.first_name}! I'm a local LLM bot.\n\n"
            f"Current model: {self._get_model(user.id)}\n\n"
            "Commands:\n"
            "/models — choose a model\n"
            "/reset — clear dialog history\n"
            "/help — show this message"
        )
```

- [ ] **Step 4: Добавить метод `reset`**

В конец класса `BotHandlers` перед `_get_model`:
```python
    async def reset(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        await self.history.reset(user.id)
        logger.info("history_reset", user_id=user.id, username=user.username)
        await update.message.reply_text("История диалога очищена.")
```

- [ ] **Step 5: Линт**

Run: `python3 -m ruff check app/bot/handlers.py`
Expected: clean.

- [ ] **Step 6: Прогнать все существующие тесты — ничего не должно сломаться**

Run: `python3 -m pytest tests/ -v`
Expected: всё зелёное.

- [ ] **Step 7: Коммит**

```bash
git add app/bot/handlers.py
git commit -m "feat(D-04): inject HistoryStore into BotHandlers + /reset"
```

---

## Task 10: Wiring в main.py

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Обновить `main.py`**

Заменить содержимое `app/main.py`:
```python
import asyncio
import signal
from pathlib import Path

import structlog
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import BotHandlers
from app.bot.middleware import LoggingMiddleware
from app.config import settings
from app.history import HistoryStore
from app.llm.client import LLMClient
from app.logging_config import setup_logging


async def run() -> None:
    setup_logging()
    logger = structlog.get_logger()
    logger.info(
        "starting_bot",
        model=settings.default_model,
        llm_url=settings.llm_base_url,
        history_dir=settings.history_dir,
        history_max_messages=settings.history_max_messages,
    )

    llm = LLMClient()
    history = HistoryStore(
        data_dir=Path(settings.history_dir),
        max_messages=settings.history_max_messages,
    )
    handlers = BotHandlers(llm=llm, history=history)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Logging middleware — logs all incoming messages
    app.add_handler(LoggingMiddleware(), group=-1)

    # Command handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("models", handlers.models))
    app.add_handler(CommandHandler("model", handlers.set_model))
    app.add_handler(CommandHandler("reset", handlers.reset))

    # Callback handler for inline keyboard (model selection)
    app.add_handler(CallbackQueryHandler(handlers.model_callback, pattern=r"^model:"))

    # Message handler (all text messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("bot_started")

    try:
        async with app:
            await app.start()
            await app.updater.start_polling()
            await stop_event.wait()
            logger.info("shutting_down")
            await app.updater.stop()
            await app.stop()
    finally:
        await llm.close()
        logger.info("bot_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Линт**

Run: `python3 -m ruff check app/`
Expected: clean.

- [ ] **Step 3: Все тесты**

Run: `python3 -m pytest tests/ -v`
Expected: всё зелёное.

- [ ] **Step 4: Коммит**

```bash
git add app/main.py
git commit -m "feat(D-04): wire HistoryStore into bot bootstrap + /reset handler"
```

---

## Task 11: docker-compose volume

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Добавить volume для bot**

```yaml
services:
  lemonade:
    build: ./lemonade
    container_name: lemonade
    ports:
      - "8000:8000"
    volumes:
      - lemonade_cache:/root/.cache
    restart: unless-stopped

  bot:
    build: .
    container_name: ai-bot
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    depends_on:
      - lemonade
    restart: unless-stopped

volumes:
  lemonade_cache:
```

- [ ] **Step 2: Коммит**

```bash
git add docker-compose.yml
git commit -m "feat(D-04): mount data/ volume for persistent dialog history"
```

---

## Task 12: Финальный прогон + manual testing

- [ ] **Step 1: Все тесты**

Run: `python3 -m pytest tests/ -v`
Expected: 11 тестов зелёные (3 старых client + 8 новых history).

- [ ] **Step 2: Lint**

Run: `python3 -m ruff check app/ tests/`
Expected: `All checks passed!`.

- [ ] **Step 3: Ручной smoke-тест**

Если бот развёрнут — выполнить в Telegram:
1. Отправить "Запомни что меня зовут Стан"
2. Отправить "Как меня зовут?" → бот должен ответить про Стана (не «не знаю»)
3. Проверить файл `data/history/{user_id}.yaml` — содержит 4 сообщения
4. `docker compose restart bot` → дождаться старта
5. Отправить "Ещё раз, как меня зовут?" → бот помнит
6. `/reset` → «История диалога очищена»
7. Отправить "Как меня зовут?" → бот не знает
8. Проверить — файла `data/history/{user_id}.yaml` нет
9. Открыть второй аккаунт, написать — проверить, что его история изолирована

Отметить результаты в `change-request.md § Checkpoints § Phase 6`.

---

## Task 13: Docs update

**Files:**
- Modify: `docs/context-dump.md`
- Modify: `docs/discuss.md`
- Modify: `docs/legacy-warning.md`
- Modify: `docs/db-schema.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ui-kit.md`
- Modify: `docs/tech-stack.md`
- Modify: `docs/tasks.md`
- Modify: `docs/current-sprint.md`
- Modify: `docs/change-request.md` (обновить блок D-04, не чистить файл)

- [ ] **Step 1: `context-dump.md` — обновить Flow 2**

Добавить в Flow 2 между шагом «Лог user_message» и «Строится messages» шаг:
```
5.5. `history_msgs = await self.history.get(user_id)` — загрузка прошлых сообщений из YAML cache/файл · [app/bot/handlers.py:handle_message]
```

И после «Лог llm_reply» шаг:
```
13.5. `await self.history.append(user_id, "user", text)` + `await self.history.append(user_id, "assistant", reply)` — только после успешного LLM ответа · [app/bot/handlers.py:handle_message]
```

- [ ] **Step 2: `context-dump.md` — добавить Flow 9: `/reset`**

В конец секции flows:
```markdown
## Flow 9 — `/reset` command

**Trigger**: пользователь пишет `/reset`.

1. `CommandHandler("reset")` → `BotHandlers.reset` · [app/bot/handlers.py](../app/bot/handlers.py)
2. `await self.history.reset(user_id)` → удаляет кэш-запись + файл `data/history/{user_id}.yaml`
3. Лог `history_reset` (user_id, username)
4. `reply_text("История диалога очищена.")`
```

- [ ] **Step 3: `discuss.md § 2` — зафиксировать решение**

Заменить секцию «## 2. Dialog history»:
```markdown
## 2. Dialog history ✅ РЕШЕНО (2026-04-15)

**Решение**: Persistent per-user YAML файлы в `data/history/{user_id}.yaml`, window default=20, команда `/reset`, system prompt не хранится в файле.

**Реализация**: D-04 (см. [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)).
```

- [ ] **Step 4: `legacy-warning.md § 4` — сузить скоуп**

Заменить заголовок и тело секции «## 4. Per-user state в памяти процесса»:
```markdown
## 4. `user_models` — per-user модель в памяти процесса
⚠ Архитектурное (by design для `user_models`, остальное state теперь персистентно)

**Где**: [app/bot/handlers.py:16](../app/bot/handlers.py)

**Что**: `self.user_models: dict[int, str] = {}`.

**Проблема**: Только выбранная модель теряется при рестарте (история диалога теперь персистентна — см. D-04). Отдельная задача D-03 покрывает persistence для моделей.

**Fix**: см. [discuss.md § 1](discuss.md#1-persistence-для-per-user-selected-model).
```

- [ ] **Step 5: `db-schema.md` — обновить «Что где хранится»**

В таблице добавить строку:
```markdown
| История диалога per-user | `data/history/{user_id}.yaml` (YAML list `{role, content}`) | Persistent (volume в docker-compose) |
```

- [ ] **Step 6: `architecture.md` — новый паттерн + edge case**

В секцию «## Паттерны» добавить после существующих:
```markdown
### 7. Per-user persistent dialog history (D-04)

`app/history/store.py` — один класс `HistoryStore`:
- YAML файлы `data/history/{user_id}.yaml` на диске, один файл = история одного пользователя
- In-memory cache (dict) + per-user `asyncio.Lock` для сериализации одновременных записей
- Sliding window по `settings.history_max_messages` (0 = без лимита)
- Команда `/reset` очищает историю юзера (удаляет файл и кэш-запись)
- System prompt не хранится в файле — всегда prepend из `SYSTEM_PROMPT` constant при LLM запросе

**Почему не БД**: для текущего scope YAML файлов хватает. Проще, диффабельнее, без миграций.
```

В секцию «## Edge cases» добавить:
```markdown
### 11. Concurrent messages от одного юзера

`HistoryStore._locks[user_id] = asyncio.Lock()`. Если пользователь шлёт 2 сообщения подряд быстрее чем первое обрабатывается, второй `append` ждёт первого. Hidden constraint: локи никогда не чистятся — минимальная утечка размером с число когда-либо активных юзеров, для self-hosted бота не проблема.

### 12. История не сохраняется при ошибке LLM

`handle_message` делает `self.history.append()` **только после** успешного `llm.chat()`. При `LLMError` user сообщение в файл не попадает, чтобы не сломать парность user/assistant в истории.
```

- [ ] **Step 7: `ui-kit.md` — команда `/reset`**

В таблицу «## Команды» добавить строку:
```markdown
| `/reset` | Очистить историю диалога пользователя | [BotHandlers.reset](../app/bot/handlers.py) |
```

В секцию «## Тексты сообщений бота» добавить:
```markdown
### `/reset` — успех
```
История диалога очищена.
```
```

Обновить текст `/start`:
```markdown
### `/start` / `/help`
```
Hello, {first_name}! I'm a local LLM bot.

Current model: {model}

Commands:
/models — choose a model
/reset — clear dialog history
/help — show this message
```
```

- [ ] **Step 8: `tech-stack.md` — PyYAML**

В таблицу «Runtime-зависимости» добавить:
```markdown
| `PyYAML` | 6.0.2 | Persistent dialog history (YAML per-user) |
```

- [ ] **Step 9: `tasks.md` — D-04 Done**

Заменить блок D-04:
```markdown
### D-04 ✅ Dialog history — persistent YAML per-user
Псевдо-память: `data/history/{user_id}.yaml`, sliding window, `/reset`. Реализовано 2026-04-15.
→ [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md)
```

- [ ] **Step 10: `current-sprint.md` — D-04 в Done**

Переместить D-04 из In Progress в Done (этот спринт).

- [ ] **Step 11: `change-request.md` — обновить статус блока D-04 на Merged**

Блок D-04 в `change-request.md` **не удаляем** — это зеркало спринта. Меняем Status на `Merged YYYY-MM-DD · commit <sha>`, отмечаем все Success criteria `[x]`, action items помечаем выполненными.

- [ ] **Step 12: Коммит docs**

```bash
git add docs/
git commit -m "docs(D-04): update architecture, flows, legacy, ui-kit, tasks, sprint board"
```

---

## Self-Review Checklist

- ✅ Spec coverage: все Success criteria из D-04 spec покрыты (Task 2-7 тесты + Task 9-10 integration + Task 11 volume + Task 12 manual + Task 13 docs)
- ✅ No placeholders
- ✅ Type consistency: `HistoryStore(data_dir: Path, max_messages: int)` везде одинаково, методы `get/append/reset` совпадают
- ✅ TDD: каждый cycle RED → GREEN → commit
- ✅ File paths absolute где нужно (relative для git add — норма)
