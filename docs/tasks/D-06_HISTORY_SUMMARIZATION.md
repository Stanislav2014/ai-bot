# D-06 · History summarization — умная обрезка контекста

| Поле | Значение |
|------|----------|
| **Task ID** | D-06 |
| **Ticket** | BOT-D06 |
| **Branch** | `feature/BAU/BOT-D06` (dependent от `feature/BAU/BOT-D05`) |
| **Status** | In Progress — Phase 0 |
| **Owner** | Stan |
| **Started** | 2026-04-15 |

---

## Summary

Когда история диалога превышает `HISTORY_SUMMARIZE_THRESHOLD` сообщений, перед отправкой в LLM старые сообщения заменяются одним кратким резюме (генерируется через отдельный LLM-запрос). Последние `HISTORY_KEEP_RECENT` сообщений остаются raw. При каждом следующем триггере старый summary сливается с новыми сообщениями в новое единое резюме — без накопления цепочек.

## Motivation

- D-04/D-05 — FIFO-обрезка: теряем смысл старых сообщений
- Для follow-up вопросов типа «как называется тот бот который мы начали делать?» — нужна память о фактах, не дословные сообщения
- Summarization сохраняет ключевые факты/решения/открытые вопросы в сжатом виде и высвобождает место в контексте под свежий диалог

Задача из Sprint 1, спрошена пользователем 2026-04-15.

---

## Design

### Архитектура

**Новый модуль** `app/history/summarizer.py` с классом `Summarizer`.
**Новый метод** `HistoryStore.replace(user_id, new_history)` — атомарный overwrite кеша + YAML файла.
**Интеграция в `BotHandlers.handle_message`** — после `history.get`, перед сборкой LLM payload.

```
app/history/
├── __init__.py            — экспорт HistoryStore, Summarizer
├── store.py               — HistoryStore (+ новый метод replace)
└── summarizer.py          — НОВЫЙ: Summarizer class
```

### Summarizer API

```python
class Summarizer:
    def __init__(
        self,
        llm: LLMClient,
        threshold: int,
        keep_recent: int,
        model: str,
    ) -> None: ...

    async def maybe_summarize(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """
        Return unchanged history if threshold not exceeded or feature disabled.
        Otherwise summarize oldest messages via LLM and return
        [summary_system_msg] + last keep_recent messages.

        Never raises — on LLM failure logs and returns original history.
        """
```

**Важно**: при неудаче LLM-вызова `maybe_summarize` **не бросает** — возвращает исходный `history`. Это гарантирует что summarization никогда не блокирует основной ответ пользователю.

### Поведение `maybe_summarize`

```python
async def maybe_summarize(self, history):
    if self._threshold <= 0 or len(history) <= self._threshold:
        return history
    split = max(0, len(history) - self._keep_recent)
    to_summarize = history[:split]
    recent = history[split:]
    if not to_summarize:
        return history  # keep_recent >= len — нечего summarize
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
```

### `_call_llm(transcript_messages)`

Формирует transcript:
```
user: Привет, я пишу Telegram-бота на Python
assistant: Звучит здорово! Что именно хочешь сделать?
user: Хочу добавить платежи
assistant: ...
```

Строит payload:
```python
prompt = [
    {
        "role": "system",
        "content": (
            "You are a conversation summarizer. Summarize the following dialog "
            "between a user and an assistant in 1-2 sentences in Russian. "
            "Preserve key facts, decisions, and open questions. "
            "Do not add commentary or meta-text. Output only the summary."
        ),
    },
    {"role": "user", "content": transcript},
]
result = await self._llm.chat(prompt, model=self._model)
return result["content"]
```

**Language**: Russian fixed (bot общение на русском по memory). Если в будущем понадобится мультиязычность — добавим detection в отдельной задаче.

### HistoryStore.replace

```python
async def replace(
    self, user_id: int, new_history: list[dict[str, str]]
) -> None:
    async with self._lock(user_id):
        self._cache[user_id] = list(new_history)
        with self._file(user_id).open("w", encoding="utf-8") as f:
            yaml.safe_dump(new_history, f, allow_unicode=True, sort_keys=False)
```

Используется только `Summarizer`-клиентом (через handlers) — прямой путь обхода `append`.

### Интеграция в handlers.py

Изменения в `handle_message` (поверх D-05):
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

Никаких изменений в `LLMError` обработке — summarizer ловит ошибки сам.

### Wiring в main.py

```python
summarizer = Summarizer(
    llm=llm,
    threshold=settings.history_summarize_threshold,
    keep_recent=settings.history_keep_recent,
    model=settings.history_summarize_model or settings.default_model,
)
handlers = BotHandlers(llm=llm, history=history, summarizer=summarizer)
```

### Config (app/config.py)

```python
history_summarize_threshold: int = 5
history_keep_recent: int = 2
history_summarize_model: str = ""  # empty → fallback to default_model
```

### .env.example

```
# Summarize history when len > threshold (0 = disabled)
HISTORY_SUMMARIZE_THRESHOLD=5

# Raw messages kept after summarization (rest becomes the summary)
HISTORY_KEEP_RECENT=2

# Model for summarization LLM call (empty = use DEFAULT_MODEL)
HISTORY_SUMMARIZE_MODEL=
```

---

## Success criteria

- [ ] `app/history/summarizer.py` с `Summarizer` классом и методом `maybe_summarize`
- [ ] `app/history/store.py` имеет метод `replace(user_id, new_history)`
- [ ] `tests/test_summarizer.py` — 8 unit тестов зелёные (mock LLM)
- [ ] `tests/test_history_store.py` — 1 новый тест `test_replace_overwrites_cache_and_file` зелёный
- [ ] Существующие тесты (3 LLM + 12 history) не сломаны
- [ ] `make test` (24 теста: 3 + 13 + 8) зелёный
- [ ] `make lint` чистый
- [ ] Env `HISTORY_SUMMARIZE_THRESHOLD=0` → feature disabled, идентично D-05 поведению
- [ ] main.py wiring передаёт summarizer в handlers; `starting_bot` лог включает `summarize_threshold`, `keep_recent`, `summarize_model`
- [ ] Ручной тест: 6+ сообщений подряд → после 6-го в `data/history/<user_id>.yaml` появляется `role: system` с summary, видно `history_summarized` в логах
- [ ] Merge в master (после D-04, D-05)

---

## Scope

### In scope
- `app/history/summarizer.py` (новый файл)
- `app/history/store.py` — `replace()` метод
- `app/history/__init__.py` — экспорт `Summarizer`
- `app/bot/handlers.py` — инъекция summarizer, вызов в handle_message
- `app/main.py` — инстанцирование Summarizer, передача в BotHandlers
- `app/config.py` — 3 новых поля
- `.env.example` — 3 env-переменных с комментариями
- `tests/test_summarizer.py` (новый, 8 тестов)
- `tests/test_history_store.py` — +1 тест на `replace`
- Docs update: architecture, context-dump Flow 2, tech-stack, legacy-warning (если нужно)

### Out of scope
- Multilingual summaries (hardcoded Russian)
- Summary quality metrics / evaluation
- Rolling-window summaries (одно summary, не цепочка)
- Per-user override threshold/model
- Streaming summary generation
- Отдельный fast model для summary (просто используем default или env-override)
- Покрытие tests для BotHandlers (не покрываются unit-тестами в проекте)

---

## Uncertainty list

1. **Key facts retention** — качество summary зависит от LLM. qwen3:0.6b может сокращать агрессивно. Если в проде качество плохое — сменить через `HISTORY_SUMMARIZE_MODEL` на более крупную модель. Не наш текущий scope.
2. **Ordering эффект recent + summary** — LLM подаётся `[SYSTEM_PROMPT, summary_system, recent..., new_user]`. Некоторые модели путаются с несколькими system. Проверим ручным тестом. Если путаница — переделать summary на role=assistant `"Previous conversation summary: ..."` (отдельная мини-задача).
3. **Идемпотентность** — если `maybe_summarize` вызван дважды подряд (race condition), второй вызов получит уже compacted history и не будет триггериться. Safe by design: проверка `len > threshold` после первого вызова будет false (так как длина после первого summarize = `1 + keep_recent`).
4. **Summary triggers on assistant append** — в D-04 handle_message делает два append: user, затем assistant. Flow: get → maybe_summarize → LLM → append user → append assistant. В момент `get` длина ещё старая (до текущего user message). Триггер работает правильно: summarize старую историю до того как append добавит текущее сообщение.
5. **Recursive summarize** — после второго триггера новый summary включает прошлый summary + новые сообщения (transcript содержит прошлую строку `system: Previous conversation summary: ...`). LLM должен сформировать единое резюме. Требует хорошего prompt — см. prompt-текст выше, уже инструктирует объединить.
6. **Размер transcript → LLM input** — если история длинная, transcript может быть большой. Но у нас FIFO D-04 (20 msg) и D-05 (8000 chars) работают как upper bound: transcript для summary ≤ ~8000 chars. Уместится в context.

---

## Test plan

**`tests/test_summarizer.py`** (new):

1. `test_maybe_summarize_below_threshold_returns_same_list`
   - threshold=5, history has 3 msgs → same list returned

2. `test_disabled_threshold_zero_always_returns_same`
   - threshold=0, history has 100 msgs → same list

3. `test_over_threshold_returns_summary_plus_recent`
   - threshold=5, keep_recent=2, history has 6 msgs, mock LLM returns "Summary text"
   - expect: `[{role:system, content:'Previous conversation summary: Summary text'}, msg5, msg6]`

4. `test_summary_message_role_is_system`
   - verify first msg of result has role=system, content prefix

5. `test_keep_recent_preserved_intact`
   - verify last keep_recent msgs in result == last keep_recent in input (byte-for-byte)

6. `test_llm_call_payload_contains_transcript`
   - mock LLM, inspect call_args; user message content includes "user: " / "assistant: " lines

7. `test_summary_llm_failure_returns_original`
   - mock LLM to raise → maybe_summarize returns original history, no exception propagated

8. `test_summary_empty_response_returns_original`
   - mock LLM returns `{"content": "   "}` → original history

**`tests/test_history_store.py`** (extend):

9. `test_replace_overwrites_cache_and_file`
   - append some → replace with new list → get returns new list → file contains new list

---

## TDD phases

### Phase 0 — Research / Design ✅
- [x] Brainstorming, вариант утверждён
- [x] Spec записан (этот файл)
- [ ] Plan записан в `D-06_HISTORY_SUMMARIZATION_plan.md`

### Phase 1 — HistoryStore.replace (TDD)
- [ ] RED: `test_replace_overwrites_cache_and_file`
- [ ] GREEN: `HistoryStore.replace`
- [ ] REFACTOR / lint

### Phase 2 — Summarizer module (TDD)
- [ ] 8 RED→GREEN циклов для тестов 1-8

### Phase 3 — Config
- [ ] `app/config.py` + `.env.example`

### Phase 4 — Wiring
- [ ] `app/main.py` инстанцирует Summarizer, передаёт в BotHandlers
- [ ] `app/bot/handlers.py` — инъекция summarizer, вызов в handle_message

### Phase 5 — Lint + full test run

### Phase 6 — Manual verification

### Phase 7 — Docs update

---

## Regression watch

- `tests/test_history_store.py` (13 после D-05) — должны оставаться зелёными
- `tests/test_llm_client.py` — не трогаем
- Handlers `handle_message` flow меняется — тесты handlers нет, ручная проверка
- Summarization вызывает extra LLM call → увеличенная latency первого ответа после триггера. Приемлемо для локальной модели.
- Если `HISTORY_SUMMARIZE_THRESHOLD=0` — ровно D-05 поведение (gate на regression)
- Failure в summarize LLM не должен ломать основной ответ (fall-through)

---

## Dependencies

- D-04 (HistoryStore existence)
- D-05 (max_chars safeguard остаётся актуален как fallback + для случаев когда summarize выключен)

---

## Links

- [change-request.md](../change-request.md) § D-06
- D-04 spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](D-04_DIALOG_HISTORY_YAML.md)
- D-05 spec: [tasks/D-05_CONTEXT_CHAR_LIMIT.md](D-05_CONTEXT_CHAR_LIMIT.md)
- [architecture.md § 1](../architecture.md) — будет расширен D-06 паттерном
- [context-dump.md Flow 2](../context-dump.md) — будет обновлён: после `history.get` шаг `maybe_summarize`

---

## History

- 2026-04-15 — task started, brainstorming done, дизайн утверждён (Summarizer class, role=system summary, default_model, fail-safe, threshold=5/keep_recent=2)
