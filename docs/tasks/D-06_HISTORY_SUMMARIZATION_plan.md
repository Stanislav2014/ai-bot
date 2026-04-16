# D-06 History Summarization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить умную обрезку истории через LLM-суммаризацию. При `len(history) > threshold` старые сообщения заменяются одним summary-сообщением (role=system), последние `keep_recent` сохраняются raw.

**Architecture:** Новый класс `Summarizer` в `app/history/summarizer.py` (fail-safe: при любой ошибке возвращает оригинальную историю). Новый метод `HistoryStore.replace()` для атомарного overwrite. Вызов из `handle_message` перед сборкой LLM payload.

**Tech Stack:** Python 3.11+, pytest-asyncio (`asyncio_mode=auto`), unittest.mock.

**Full spec:** [D-06_HISTORY_SUMMARIZATION.md](D-06_HISTORY_SUMMARIZATION.md)

---

## File structure

```
app/history/summarizer.py         NEW · Summarizer class
app/history/__init__.py           MODIFY · export Summarizer
app/history/store.py              MODIFY · +replace() method
app/bot/handlers.py               MODIFY · inject summarizer, call in handle_message
app/main.py                       MODIFY · instantiate Summarizer, wire into BotHandlers
app/config.py                     MODIFY · +history_summarize_threshold/keep_recent/model
.env.example                      MODIFY · +3 env vars
tests/test_summarizer.py          NEW · 8 tests
tests/test_history_store.py       MODIFY · +1 test for replace()
```

---

## Task 1: HistoryStore.replace (TDD)

**Files:**
- Modify: `tests/test_history_store.py`
- Modify: `app/history/store.py`

- [ ] **Step 1: Падающий тест**

В `tests/test_history_store.py`:
```python
async def test_replace_overwrites_cache_and_file(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "old")
    new_history = [
        {"role": "system", "content": "Summary X"},
        {"role": "user", "content": "latest"},
    ]
    await store.replace(1, new_history)
    assert await store.get(1) == new_history
    # Persisted: new HistoryStore instance reads same
    s2 = HistoryStore(history_dir, max_messages=20)
    assert await s2.get(1) == new_history
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m pytest tests/test_history_store.py::test_replace_overwrites_cache_and_file -v`
Expected: FAIL — `AttributeError: ... replace`.

- [ ] **Step 3: Реализовать `replace`**

В `app/history/store.py` после `reset`:
```python
    async def replace(
        self, user_id: int, new_history: list[dict[str, str]]
    ) -> None:
        async with self._lock(user_id):
            self._cache[user_id] = list(new_history)
            with self._file(user_id).open("w", encoding="utf-8") as f:
                yaml.safe_dump(new_history, f, allow_unicode=True, sort_keys=False)
```

- [ ] **Step 4: Прогнать — зелёный**

Run: `python3 -m pytest tests/test_history_store.py -v`
Expected: 13 passed (12 existing + 1 new).

- [ ] **Step 5: Коммит**

```bash
git add app/history/store.py tests/test_history_store.py
git commit -m "feat(D-06): HistoryStore.replace for atomic overwrite of user history"
```

---

## Task 2: Summarizer skeleton + below-threshold tests

**Files:**
- Create: `app/history/summarizer.py`
- Modify: `app/history/__init__.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Создать `app/history/summarizer.py` (минимальный)**

```python
import structlog

from app.llm.client import LLMClient

logger = structlog.get_logger()

SUMMARY_PROMPT = (
    "You are a conversation summarizer. Summarize the following dialog "
    "between a user and an assistant in 1-2 sentences in Russian. "
    "Preserve key facts, decisions, and open questions. "
    "Do not add commentary or meta-text. Output only the summary."
)


class Summarizer:
    def __init__(
        self,
        llm: LLMClient,
        threshold: int,
        keep_recent: int,
        model: str,
    ) -> None:
        self._llm = llm
        self._threshold = threshold
        self._keep_recent = keep_recent
        self._model = model

    async def maybe_summarize(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        if self._threshold <= 0 or len(history) <= self._threshold:
            return history
        return history  # stub — filled in Task 3
```

- [ ] **Step 2: Обновить `app/history/__init__.py`**

```python
from app.history.store import HistoryStore
from app.history.summarizer import Summarizer

__all__ = ["HistoryStore", "Summarizer"]
```

- [ ] **Step 3: Написать 2 теста (ниже threshold / disabled)**

Создать `tests/test_summarizer.py`:
```python
from unittest.mock import AsyncMock

import pytest

from app.history import Summarizer


@pytest.fixture
def llm_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value={"content": "Summary text", "tokens_used": 10})
    return mock


async def test_maybe_summarize_below_threshold_returns_same_list(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=5, keep_recent=2, model="test-model")
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = await summarizer.maybe_summarize(history)
    assert result is history
    llm_mock.chat.assert_not_called()


async def test_disabled_threshold_zero_always_returns_same(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=0, keep_recent=2, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(100)]
    result = await summarizer.maybe_summarize(history)
    assert result is history
    llm_mock.chat.assert_not_called()
```

- [ ] **Step 4: Прогнать**

Run: `python3 -m pytest tests/test_summarizer.py -v`
Expected: 2 passed.

- [ ] **Step 5: Lint**

Run: `python3 -m ruff check app/history tests/test_summarizer.py`
Expected: `All checks passed!`.

- [ ] **Step 6: Коммит**

```bash
git add app/history/summarizer.py app/history/__init__.py tests/test_summarizer.py
git commit -m "feat(D-06): Summarizer skeleton — returns history unchanged when below threshold"
```

---

## Task 3: Summarizer happy path (RED → GREEN)

**Files:**
- Modify: `tests/test_summarizer.py`
- Modify: `app/history/summarizer.py`

- [ ] **Step 1: Падающий тест — over threshold returns summary + recent**

Добавить в `tests/test_summarizer.py`:
```python
async def test_over_threshold_returns_summary_plus_recent(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=5, keep_recent=2, model="test-model")
    history = [
        {"role": "user", "content": f"m{i}"} for i in range(6)
    ]
    result = await summarizer.maybe_summarize(history)
    assert len(result) == 3  # 1 summary + 2 recent
    assert result[0] == {
        "role": "system",
        "content": "Previous conversation summary: Summary text",
    }
    assert result[1] == {"role": "user", "content": "m4"}
    assert result[2] == {"role": "user", "content": "m5"}
    llm_mock.chat.assert_called_once()
```

- [ ] **Step 2: Прогнать — падает (stub returns original)**

Run: `python3 -m pytest tests/test_summarizer.py::test_over_threshold_returns_summary_plus_recent -v`
Expected: FAIL — `assert len(result) == 3` fails with `6 == 3`.

- [ ] **Step 3: Реализовать логику**

Заменить `maybe_summarize` в `app/history/summarizer.py`:
```python
    async def maybe_summarize(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        if self._threshold <= 0 or len(history) <= self._threshold:
            return history
        split = max(0, len(history) - self._keep_recent)
        to_summarize = history[:split]
        recent = history[split:]
        if not to_summarize:
            return history
        try:
            summary_text = await self._call_llm(to_summarize)
        except Exception:
            logger.exception("summarize_failed")
            return history
        summary_text = summary_text.strip()
        if not summary_text:
            logger.warning("summarize_empty_response")
            return history
        summary_msg = {
            "role": "system",
            "content": f"Previous conversation summary: {summary_text}",
        }
        return [summary_msg] + recent

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        transcript = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )
        prompt = [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": transcript},
        ]
        result = await self._llm.chat(prompt, model=self._model)
        return result["content"]
```

- [ ] **Step 4: Прогнать — зелёный**

Run: `python3 -m pytest tests/test_summarizer.py -v`
Expected: 3 passed.

- [ ] **Step 5: Коммит**

```bash
git add app/history/summarizer.py tests/test_summarizer.py
git commit -m "feat(D-06): Summarizer replaces oldest messages with LLM-generated summary"
```

---

## Task 4: Additional behavior tests (role, keep_recent, payload, failures)

**Files:**
- Modify: `tests/test_summarizer.py`

- [ ] **Step 1: Добавить 5 тестов**

```python
async def test_summary_message_role_is_system(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result[0]["role"] == "system"
    assert result[0]["content"].startswith("Previous conversation summary: ")


async def test_keep_recent_preserved_intact(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=2, model="test-model")
    history = [
        {"role": "user", "content": "m0"},
        {"role": "assistant", "content": "m1"},
        {"role": "user", "content": "m2"},
        {"role": "assistant", "content": "m3"},
        {"role": "user", "content": "m4"},
    ]
    result = await summarizer.maybe_summarize(history)
    # last 2 untouched
    assert result[-2] == {"role": "assistant", "content": "m3"}
    assert result[-1] == {"role": "user", "content": "m4"}


async def test_llm_call_payload_contains_transcript(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=2, keep_recent=1, model="test-model")
    history = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуй"},
        {"role": "user", "content": "Как дела?"},
    ]
    await summarizer.maybe_summarize(history)
    call_args = llm_mock.chat.call_args
    payload = call_args.args[0]  # messages list
    assert payload[0]["role"] == "system"
    user_content = payload[1]["content"]
    assert "user: Привет" in user_content
    assert "assistant: Здравствуй" in user_content
    assert call_args.kwargs["model"] == "test-model"


async def test_summary_llm_failure_returns_original(llm_mock: AsyncMock) -> None:
    llm_mock.chat = AsyncMock(side_effect=RuntimeError("boom"))
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result is history


async def test_summary_empty_response_returns_original(llm_mock: AsyncMock) -> None:
    llm_mock.chat = AsyncMock(return_value={"content": "   \n  "})
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result is history
```

- [ ] **Step 2: Прогнать все summarizer тесты**

Run: `python3 -m pytest tests/test_summarizer.py -v`
Expected: 8 passed.

- [ ] **Step 3: Lint**

Run: `python3 -m ruff check app/history tests/test_summarizer.py`
Expected: clean.

- [ ] **Step 4: Коммит**

```bash
git add tests/test_summarizer.py
git commit -m "test(D-06): Summarizer role, keep_recent, payload, failure, empty-response"
```

---

## Task 5: Config + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Добавить 3 поля в Settings**

```python
    history_dir: str = "data/history"
    history_max_messages: int = 20
    history_max_chars: int = 8000
    history_summarize_threshold: int = 5
    history_keep_recent: int = 2
    history_summarize_model: str = ""
```

- [ ] **Step 2: `.env.example`**

```
# Max total chars in dialog history (0 = unlimited)
HISTORY_MAX_CHARS=8000

# Summarize history when len > threshold (0 = disabled)
HISTORY_SUMMARIZE_THRESHOLD=5

# Raw messages kept after summarization
HISTORY_KEEP_RECENT=2

# Model for summarization LLM call (empty = use DEFAULT_MODEL)
HISTORY_SUMMARIZE_MODEL=
```

- [ ] **Step 3: Прогнать все тесты**

Run: `python3 -m pytest tests/ -v`
Expected: 24 passed (3 LLM + 13 history + 8 summarizer).

- [ ] **Step 4: Коммит**

```bash
git add app/config.py .env.example
git commit -m "feat(D-06): config history_summarize_threshold / keep_recent / model"
```

---

## Task 6: BotHandlers + main.py wiring

**Files:**
- Modify: `app/bot/handlers.py`
- Modify: `app/main.py`

- [ ] **Step 1: Инъекция summarizer в BotHandlers**

В `app/bot/handlers.py`, изменить импорты и `__init__`:
```python
from app.history import HistoryStore, Summarizer
```

```python
class BotHandlers:
    def __init__(
        self,
        llm: LLMClient,
        history: HistoryStore,
        summarizer: Summarizer,
    ) -> None:
        self.llm = llm
        self.history = history
        self.summarizer = summarizer
        self.user_models: dict[int, str] = {}
```

- [ ] **Step 2: Вызов summarizer в handle_message**

Найти блок:
```python
        history_msgs = await self.history.get(user_id)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history_msgs
            + [{"role": "user", "content": text}]
        )
```

Заменить на:
```python
        history_msgs = await self.history.get(user_id)
        new_history = await self.summarizer.maybe_summarize(history_msgs)
        if new_history is not history_msgs:
            await self.history.replace(user_id, new_history)
            logger.info(
                "history_summarized",
                user_id=user_id,
                before=len(history_msgs),
                after=len(new_history),
            )
            history_msgs = new_history
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history_msgs
            + [{"role": "user", "content": text}]
        )
```

- [ ] **Step 3: Инстанцировать Summarizer в main.py**

В `app/main.py` после создания `history`:
```python
    from app.history import HistoryStore, Summarizer
    ...
    history = HistoryStore(
        data_dir=Path(settings.history_dir),
        max_messages=settings.history_max_messages,
        max_chars=settings.history_max_chars,
    )
    summarizer = Summarizer(
        llm=llm,
        threshold=settings.history_summarize_threshold,
        keep_recent=settings.history_keep_recent,
        model=settings.history_summarize_model or settings.default_model,
    )
    handlers = BotHandlers(llm=llm, history=history, summarizer=summarizer)
```

И в `starting_bot` лог добавить:
```python
    logger.info(
        "starting_bot",
        model=settings.default_model,
        llm_url=settings.llm_base_url,
        history_dir=settings.history_dir,
        history_max_messages=settings.history_max_messages,
        history_max_chars=settings.history_max_chars,
        summarize_threshold=settings.history_summarize_threshold,
        keep_recent=settings.history_keep_recent,
        summarize_model=settings.history_summarize_model or settings.default_model,
    )
```

- [ ] **Step 4: Lint + smoke import**

Run: `python3 -m ruff check app/ tests/ && python3 -c "from app.main import run; print('ok')"`
Expected: clean + ok.

- [ ] **Step 5: Прогнать все тесты**

Run: `python3 -m pytest tests/ -v`
Expected: 24 passed.

- [ ] **Step 6: Коммит**

```bash
git add app/bot/handlers.py app/main.py
git commit -m "feat(D-06): wire Summarizer into BotHandlers and startup"
```

---

## Task 7: Docs update

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/context-dump.md`
- Modify: `docs/tech-stack.md`
- Modify: `docs/tasks.md`
- Modify: `docs/current-sprint.md`
- Modify: `docs/change-request.md`

- [ ] **Step 1: `architecture.md` § 1 — упомянуть summarizer**

Найти секцию «### 1. Per-user dialog history с YAML персистенцией (D-04)» и после bullet про char budget (D-05) добавить:

```markdown
- **summarization** (D-06): перед сборкой LLM payload `Summarizer.maybe_summarize()` проверяет `len(history) > settings.history_summarize_threshold` (0 = disabled). Если триггер — старые сообщения уходят в отдельный LLM-запрос на summary, результат заменяет их single system-message `"Previous conversation summary: ..."`, последние `HISTORY_KEEP_RECENT` сообщений остаются raw. Fail-safe: при любой ошибке LLM summarizer возвращает оригинальную историю.
```

- [ ] **Step 2: `architecture.md` — добавить edge case**

В секцию «## Edge cases» добавить:

```markdown
### 15. Summarization recursive merge

При каждом триггере Summarizer подаёт LLM полный transcript текущих «старых» сообщений, включая прошлый summary (если он был первым элементом). Prompt просит объединить в одно резюме — цепочка summaries не накапливается. Если LLM отдаст плохой merge (например, проигнорирует прошлый summary) — факты теряются. В проде смотрим поле `history_summarized.before`/`after` в логах + периодически проверяем `data/history/*.yaml`.
```

- [ ] **Step 3: `context-dump.md` Flow 2 — добавить шаг summarize**

Найти в Flow 2 между шагом «history_msgs = await self.history.get(user_id)» и «Строится messages = [system] + history_msgs + [new_user]» добавить:

```markdown
6.5. **`new_history = await self.summarizer.maybe_summarize(history_msgs)`** — если `len > threshold` (D-06), старые сообщения → LLM summary call → `[summary_system_msg] + keep_recent`. Если summary — новая история → `await self.history.replace(user_id, new_history)` + log `history_summarized`. Если ошибка/disabled — возвращается `history_msgs` без изменений.
```

- [ ] **Step 4: `tech-stack.md` env table**

Добавить 3 строки:
```markdown
| `HISTORY_SUMMARIZE_THRESHOLD` | 5 | Суммаризировать при `len(history) > threshold` (0 = disabled) |
| `HISTORY_KEEP_RECENT` | 2 | Сколько последних raw сообщений сохранить после суммаризации |
| `HISTORY_SUMMARIZE_MODEL` | `""` | Модель для summary LLM-запроса (пусто = DEFAULT_MODEL) |
```

- [ ] **Step 5: `tasks.md` — D-06 ✅**

Заменить блок D-06 (после paperwork Phase 0 будет добавлен):
```markdown
### D-06 ✅ History summarization — умная обрезка через LLM
Summarizer класс: при `len > HISTORY_SUMMARIZE_THRESHOLD` (default 5) старые сообщения заменяются single summary-system-message через LLM-запрос; последние `HISTORY_KEEP_RECENT` сохраняются raw. Fail-safe. D-04/D-05 работают как fallback.
Branch: `feature/BAU/BOT-D06` · code complete 2026-04-15 · 24/24 tests green
→ [tasks/D-06_HISTORY_SUMMARIZATION.md](tasks/D-06_HISTORY_SUMMARIZATION.md)
```

- [ ] **Step 6: `current-sprint.md` — D-06 в In Review / Done**

Перенести D-06 из In Progress в In Review (awaiting smoke-test) или Done (этот спринт).

- [ ] **Step 7: `change-request.md` — обновить блок D-06**

Отметить Success criteria как `[x]`, action items как выполненные, добавить Phase checkpoint.

- [ ] **Step 8: Коммит**

```bash
git add docs/
git commit -m "docs(D-06): record summarizer pattern, Flow 2 step, env table, board"
```

---

## Task 8: Manual verification (после merge D-04, D-05)

- [ ] **Step 1: Rebuild + restart**

```bash
make build && make restart
```

- [ ] **Step 2: Проверить `starting_bot` log**

Run: `docker compose logs --tail=5 bot | grep starting_bot`
Expected: поля `summarize_threshold: 5`, `keep_recent: 2`, `summarize_model`.

- [ ] **Step 3: Ручной smoke в Telegram**

- `/reset` — очистить историю текущего юзера
- Отправить 6 осмысленных сообщений подряд (пары вопрос/ответ: 3 запроса пользователя + 3 ответа бота):
  1. «Я разрабатываю Telegram-бота на Python»
  2. (ответ бота)
  3. «Хочу добавить платежи через ЮKassa»
  4. (ответ бота)
  5. «Какой самый простой способ хранить подписки?»
  6. (ответ бота)
- После 6-го сообщения проверить `cat data/history/356640470.yaml` — первым элементом должен быть `role: system` с `content: "Previous conversation summary: ..."` на русском. Последние 2 сообщения — raw.
- Отправить 7-е: «Напомни, что мы обсуждаем?» — бот должен ссылаться на Python-бота / платежи / подписки через summary.
- В `docker compose logs bot` видно event `history_summarized` с полями `before: 6, after: 3`.

- [ ] **Step 4: Обновить `change-request.md` блок D-06 — отметить smoke-test passed**

---

## Self-Review

- ✅ Spec coverage: все Success criteria из D-06 spec покрыты (Task 1-7)
- ✅ No placeholders
- ✅ Type consistency: `Summarizer(llm, threshold, keep_recent, model)` everywhere; `maybe_summarize(history) -> list[dict]`
- ✅ TDD: Task 1 + Task 3 имеют явные RED→GREEN циклы; Task 4 дополняет behavioral coverage
- ✅ Backwards compat: `threshold=0` → exact D-05 behavior (gate на regression)
- ✅ Fail-safe: `maybe_summarize` никогда не бросает (тест `test_summary_llm_failure_returns_original`)
