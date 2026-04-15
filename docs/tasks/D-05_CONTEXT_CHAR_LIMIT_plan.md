# D-05 Context char limit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить второй safeguard на размер истории диалога — по суммарной длине текста (chars). Работает поверх D-04 count limit.

**Architecture:** Один новый kwarg `max_chars` в `HistoryStore.__init__` + расширение `append()` char-trim логикой после count-trim. Новый env `HISTORY_MAX_CHARS` (default 8000, 0 = disabled). Обратно совместимо.

**Tech Stack:** Python 3.11+, pytest-asyncio (asyncio_mode=auto), structlog.

**Full spec:** [D-05_CONTEXT_CHAR_LIMIT.md](D-05_CONTEXT_CHAR_LIMIT.md)

---

## File structure

```
app/history/store.py              MODIFY · +max_chars kwarg, char-trim in append
app/config.py                     MODIFY · +history_max_chars
app/main.py                       MODIFY · pass max_chars to HistoryStore
.env.example                      MODIFY · +HISTORY_MAX_CHARS
tests/test_history_store.py       MODIFY · +4 tests
```

---

## Task 1: char-trim — disabled by default (backwards compat test)

**Files:**
- Modify: `app/history/store.py`
- Modify: `tests/test_history_store.py`

- [ ] **Step 1: Расширить `HistoryStore.__init__` новым kwarg**

В `app/history/store.py`:
```python
class HistoryStore:
    def __init__(self, data_dir: Path, max_messages: int, max_chars: int = 0) -> None:
        self._data_dir = data_dir
        self._max_messages = max_messages
        self._max_chars = max_chars
        self._cache: dict[int, list[dict[str, str]]] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._data_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Прогнать существующие 8 тестов — должны пройти (обратная совместимость)**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: 8 passed.

- [ ] **Step 3: Коммит (API-extension без изменения поведения)**

```bash
git add app/history/store.py
git commit -m "feat(D-05): add max_chars kwarg to HistoryStore (disabled by default)"
```

---

## Task 2: char-trim logic (RED → GREEN)

**Files:**
- Modify: `tests/test_history_store.py`
- Modify: `app/history/store.py`

- [ ] **Step 1: Добавить падающий тест — char trim**

```python
async def test_char_limit_trims_oldest_when_over_budget(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20, max_chars=50)
    # Append 10 messages, each content length 10 → total 100 chars, exceeds 50
    for i in range(10):
        await store.append(1, "user", f"m{i:08d}")  # exactly 10 chars: "m00000000"
    result = await store.get(1)
    total = sum(len(m["content"]) for m in result)
    assert total <= 50
    # At least the last message must remain
    assert result[-1]["content"] == "m00000009"
    # And removing one more oldest would bring us further from the budget
    # (i.e. we stopped at the smallest allowable trim)
    assert total + 10 > 50
```

- [ ] **Step 2: Запустить — должен упасть (логика не реализована)**

Run: `python3 -m pytest tests/test_history_store.py::test_char_limit_trims_oldest_when_over_budget -v`
Expected: FAIL — `total > 50`.

- [ ] **Step 3: Реализовать char-trim в `append`**

Заменить тело `append` (после существующего count-trim) в `app/history/store.py`:
```python
    async def append(self, user_id: int, role: str, content: str) -> None:
        async with self._lock(user_id):
            if user_id not in self._cache:
                self._cache[user_id] = self._load_from_disk(user_id)
            history = self._cache[user_id]
            history.append({"role": role, "content": content})
            if self._max_messages > 0 and len(history) > self._max_messages:
                history = history[-self._max_messages :]
            if self._max_chars > 0:
                while len(history) > 1 and _total_chars(history) > self._max_chars:
                    history = history[1:]
            self._cache[user_id] = history
            with self._file(user_id).open("w", encoding="utf-8") as f:
                yaml.safe_dump(history, f, allow_unicode=True, sort_keys=False)
```

И добавить helper после импортов или внутри файла:
```python
def _total_chars(history: list[dict[str, str]]) -> int:
    return sum(len(m["content"]) for m in history)
```

**Важно**: после count-trim `history` — новый список (slice). Присваивать обратно в `self._cache[user_id] = history` надо **один раз** после всех trim-ов (см. код выше).

- [ ] **Step 4: Прогнать тест — зелёный**

Run: `python3 -m pytest tests/test_history_store.py::test_char_limit_trims_oldest_when_over_budget -v`
Expected: PASS.

- [ ] **Step 5: Прогнать все тесты HistoryStore — обратная совместимость**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: 9 passed.

- [ ] **Step 6: Коммит**

```bash
git add app/history/store.py tests/test_history_store.py
git commit -m "feat(D-05): char-budget trim in HistoryStore.append (FIFO)"
```

---

## Task 3: Edge cases — disabled + last-message-oversize + combined

**Files:**
- Modify: `tests/test_history_store.py`

- [ ] **Step 1: Добавить три теста**

```python
async def test_char_limit_zero_means_disabled(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=200, max_chars=0)
    long = "x" * 1000
    for i in range(50):
        await store.append(1, "user", long)
    result = await store.get(1)
    assert len(result) == 50


async def test_char_limit_keeps_last_when_single_message_over_budget(
    history_dir: Path,
) -> None:
    store = HistoryStore(history_dir, max_messages=20, max_chars=10)
    huge = "x" * 100
    await store.append(1, "user", huge)
    result = await store.get(1)
    assert len(result) == 1
    assert result[0]["content"] == huge


async def test_char_and_count_limits_combined(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=5, max_chars=100)
    # 10 messages, each 30 chars
    for i in range(10):
        await store.append(1, "user", "x" * 30)
    result = await store.get(1)
    # count-trim leaves last 5 (150 chars) → char-trim drops until ≤100 → 3 messages = 90 chars
    assert len(result) == 3
    assert sum(len(m["content"]) for m in result) == 90
```

- [ ] **Step 2: Прогнать все**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: 12 passed (8 old + 1 from Task 2 + 3 from this task).

- [ ] **Step 3: Lint**

Run: `python3 -m ruff check app/history tests/test_history_store.py`
Expected: `All checks passed!`.

- [ ] **Step 4: Коммит**

```bash
git add tests/test_history_store.py
git commit -m "test(D-05): char limit edge cases — disabled, oversize single, combined"
```

---

## Task 4: Config + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Добавить поле в `app/config.py`**

```python
class Settings(BaseSettings):
    telegram_bot_token: str
    llm_base_url: str = "http://ollama:11434"
    default_model: str = "qwen3:0.6b"
    llm_timeout: int = 120
    log_level: str = "INFO"
    history_dir: str = "data/history"
    history_max_messages: int = 20
    history_max_chars: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

- [ ] **Step 2: Добавить в `.env.example`**

В конец:
```
# Max total chars in dialog history (0 = unlimited)
HISTORY_MAX_CHARS=8000
```

- [ ] **Step 3: Прогнать тесты (защита от breakage config import)**

Run: `python3 -m pytest tests/ -v`
Expected: 14 passed (3 LLM + 11 history).

Wait — 12 history tests, not 11. Итого 15. _(поправка: 3 + 12 = 15)_

- [ ] **Step 4: Коммит**

```bash
git add app/config.py .env.example
git commit -m "feat(D-05): config history_max_chars (default 8000)"
```

---

## Task 5: main.py wiring

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Передать `max_chars` в HistoryStore**

```python
    history = HistoryStore(
        data_dir=Path(settings.history_dir),
        max_messages=settings.history_max_messages,
        max_chars=settings.history_max_chars,
    )
```

И в логе старта добавить поле:
```python
    logger.info(
        "starting_bot",
        model=settings.default_model,
        llm_url=settings.llm_base_url,
        history_dir=settings.history_dir,
        history_max_messages=settings.history_max_messages,
        history_max_chars=settings.history_max_chars,
    )
```

- [ ] **Step 2: Lint + smoke import**

Run: `python3 -m ruff check app/ tests/ && python3 -c "from app.main import run; print('ok')"`
Expected: `All checks passed!` + `ok`.

- [ ] **Step 3: Коммит**

```bash
git add app/main.py
git commit -m "feat(D-05): wire history_max_chars into HistoryStore bootstrap"
```

---

## Task 6: Docs update

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/context-dump.md`
- Modify: `docs/tech-stack.md`
- Modify: `docs/tasks.md`
- Modify: `docs/current-sprint.md`
- Modify: `docs/change-request.md`

- [ ] **Step 1: `architecture.md` — упомянуть двухступенчатый trim**

Найти секцию «### 1. Per-user dialog history с YAML персистенцией (D-04)», после строки «- sliding window через `settings.history_max_messages` (0 = без лимита)» добавить:

```markdown
- **char budget** (D-05): после count-trim дополнительно режет FIFO пока `sum(len(content)) ≤ settings.history_max_chars` (0 = без лимита). Защита от одного длинного сообщения, переполняющего context window.
```

- [ ] **Step 2: `context-dump.md` — упомянуть в Flow 2**

Найти в Flow 2 шаг 15 (append assistant), добавить комментарий:
```
(append применяет count-trim и char-trim FIFO — см. HistoryStore.append)
```

- [ ] **Step 3: `tech-stack.md` — добавить HISTORY_MAX_CHARS**

В таблицу env-переменных строку:
```markdown
| `HISTORY_MAX_CHARS` | 8000 | Макс суммарная длина истории в символах (0 = без лимита) |
```

- [ ] **Step 4: `tasks.md` — пометить D-05 Done**

Заменить блок D-05 (будет уже добавлен в Phase 0 paperwork) на:
```markdown
### D-05 ✅ Context char limit — второй safeguard
Кап по суммарной длине истории (`HISTORY_MAX_CHARS`, default 8000). Работает поверх `HISTORY_MAX_MESSAGES`. FIFO-trim защищает от одной длинной простыни, переполняющей context window. Merged 2026-04-15.
→ [tasks/D-05_CONTEXT_CHAR_LIMIT.md](tasks/D-05_CONTEXT_CHAR_LIMIT.md)
```

- [ ] **Step 5: `current-sprint.md` — D-05 в Done**

Переместить D-05 из In Progress в Done (этот спринт).

- [ ] **Step 6: `change-request.md` — обновить статус D-05 блока**

Не чистить, а пометить Status: `Merged YYYY-MM-DD · commit <sha>`, все Success criteria `[x]`, action items выполнены.

- [ ] **Step 7: Коммит docs**

```bash
git add docs/
git commit -m "docs(D-05): record context char limit in architecture, flows, board"
```

---

## Task 7: Manual verification

- [ ] **Step 1: Rebuild + restart**

```bash
make build && make restart
```

- [ ] **Step 2: Логи — убедиться что `history_max_chars` видно в `starting_bot` event**

Run: `docker compose logs --tail=5 bot | grep starting_bot`
Expected: `"history_max_chars": 8000`.

- [ ] **Step 3: В Telegram**

- Отправить 3-4 очень длинных сообщения (по 3000 chars каждое)
- После четвёртого проверить `cat data/history/<user_id>.yaml` — общая длина не должна превышать 8000 chars
- Отправить ещё одно обычное сообщение — предыдущие должны подрезаться так чтобы общий бюджет соблюдался

---

## Self-Review

- ✅ Spec coverage: `max_chars` API, 4 tests, config, wiring, docs — все из D-05 spec
- ✅ No placeholders
- ✅ Type consistency: `max_chars: int = 0` везде
- ✅ TDD: Task 2 RED → GREEN, Task 3 дополняет edge cases
- ✅ Backwards compat: Task 1 проверяет что default=0 не ломает старые тесты
