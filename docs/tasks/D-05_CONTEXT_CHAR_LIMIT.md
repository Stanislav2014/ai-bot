# D-05 · Context char limit — второй safeguard для размера истории

| Поле | Значение |
|------|----------|
| **Task ID** | D-05 |
| **Ticket** | BOT-D05 |
| **Branch** | `feature/BAU/BOT-D05` (создаётся от `master` после merge D-04, или от `feature/BAU/BOT-D04` если ещё не merged) |
| **Status** | In Progress — Phase 0 |
| **Owner** | Stan |
| **Started** | 2026-04-15 |

---

## Summary

Добавить второе ограничение на размер истории диалога: по суммарной длине текста (chars). Работает **поверх** существующего ограничения по количеству сообщений (`HISTORY_MAX_MESSAGES` из D-04). Защита от одной длинной простыни, которая влезает в 20 сообщений, но переполняет context window модели.

## Motivation

D-04 ограничивает историю 20-ю сообщениями. Но одно из этих сообщений может быть на 15k символов — и контекст улетает в тысячи токенов, LLM падает с `context length exceeded`. Нужен второй safeguard: кап по сумме `len(content)` всех сообщений.

Спрошено пользователем 2026-04-15 как task 2 в Sprint 1.

---

## Design

### HistoryStore API change

```python
class HistoryStore:
    def __init__(
        self,
        data_dir: Path,
        max_messages: int,
        max_chars: int = 0,   # NEW: 0 = disabled
    ) -> None: ...
```

Новый kwarg `max_chars` с дефолтом `0` (disabled) — обратно совместимо, все существующие вызовы `HistoryStore(dir, max_messages=N)` продолжают работать.

### Trim logic в `append()`

Сейчас:
```python
history.append({"role": role, "content": content})
if self._max_messages > 0 and len(history) > self._max_messages:
    history = history[-self._max_messages:]
```

Становится:
```python
history.append({"role": role, "content": content})
if self._max_messages > 0 and len(history) > self._max_messages:
    history = history[-self._max_messages:]
if self._max_chars > 0:
    while len(history) > 1 and _total_chars(history) > self._max_chars:
        history = history[1:]
```

`_total_chars(history)` = `sum(len(m["content"]) for m in history)`.

**Порядок важен**: count-trim **первый**, char-trim **второй**. Причина: count режет до N сообщений → потом char-trim режет до <max_chars.

**Edge case**: если последнее (только что добавленное) сообщение **само** > max_chars — оставляем его, режем пустой tail. `while len(history) > 1` защищает от дропа единственного сообщения. LLM получит одно огромное сообщение и, возможно, упадёт с context error — но это лучше чем терять только что пришедший user input. В логе warning.

### Config

`app/config.py`:
```python
history_max_chars: int = 8000   # 0 = unlimited
```

Дефолт 8000 chars ≈ 2000 токенов — safely fits в context window даже младшего qwen3:0.6b (8k context).

`.env.example`:
```
# Max total chars in dialog history (0 = unlimited)
HISTORY_MAX_CHARS=8000
```

### main.py wiring

```python
history = HistoryStore(
    data_dir=Path(settings.history_dir),
    max_messages=settings.history_max_messages,
    max_chars=settings.history_max_chars,
)
```

### Интеграция в handlers.py

Никаких изменений — `HistoryStore` инкапсулирует логику.

### Тесты (`tests/test_history_store.py`)

Новые тесты поверх существующих:

1. **`test_char_limit_trims_oldest_when_over_budget`**
   - `max_messages=20, max_chars=50`
   - Append 10 сообщений по 10 символов (100 > 50)
   - Expect: остались последние N сообщений, `total_chars ≤ 50`, и `total_chars + len(dropped_oldest) > 50` (точность trim)

2. **`test_char_limit_zero_means_disabled`**
   - `max_chars=0`
   - Append 100 больших сообщений
   - Expect: все 100 в истории (ограничены только count-лимитом если задан)

3. **`test_char_limit_keeps_last_when_single_message_over_budget`**
   - `max_messages=20, max_chars=10`
   - Append одно сообщение на 100 символов
   - Expect: `len(history) == 1`, содержит это сообщение (не дропнули несмотря на превышение)

4. **`test_char_and_count_limits_combined`**
   - `max_messages=5, max_chars=100`
   - Append 10 сообщений по 30 символов каждое
   - Ожидание: count-trim оставил 5 (150 chars), char-trim режет до ≤100 → 3 сообщения по 30 = 90 chars
   - Проверка: `len == 3`, `total_chars == 90`

### Error handling

Нет новых путей ошибок — логика синхронная и не зависит от I/O.

Опционально: лог `history_char_trimmed` когда char-trim сработал, `history_single_message_oversize` когда одиночное сообщение превышает лимит.

---

## Success criteria (verifiable)

- [ ] 4 новых unit теста зелёные
- [ ] Существующие 8 тестов HistoryStore не сломаны (обратная совместимость `max_chars=0` default)
- [ ] `make test` зелёный (всего 15 тестов: 3 LLM + 8 старых history + 4 новых char)
- [ ] `make lint` зелёный
- [ ] `settings.history_max_chars` доступен через env `HISTORY_MAX_CHARS`
- [ ] `.env.example` содержит документацию `HISTORY_MAX_CHARS`
- [ ] `main.py` передаёт `max_chars` в HistoryStore
- [ ] Ручная проверка: в Telegram отправить очень длинное сообщение (5000 chars) 3 раза подряд → четвёртое сообщение LLM получает историю ≤8000 chars

---

## Scope

### In scope
- `app/history/store.py` — добавить `max_chars` kwarg + char-trim логика в `append`
- `app/config.py` — `history_max_chars`
- `app/main.py` — wiring
- `.env.example` — `HISTORY_MAX_CHARS`
- `tests/test_history_store.py` — 4 новых теста
- Docs update: architecture.md edge case, context-dump.md Flow 2, tech-stack.md env table, legacy-warning.md если нужно
- change-request.md, tasks.md, current-sprint.md — post-merge обновление

### Out of scope
- Токен-based ограничение (нет tokenizer'а, добавим только если chars окажется плохим прокси)
- Compression/summarization старых сообщений
- Per-model context window детектирование (статика `HISTORY_MAX_CHARS` в env)
- Обрезка отдельного сообщения внутри его content (только FIFO по целым сообщениям)

---

## Uncertainty list

1. **Char vs token** — `len(content)` даёт chars, не токены. Соотношение зависит от модели (qwen3: ~4 chars/token для латиницы, ~2 для кириллицы). Дефолт 8000 chars = 2000-4000 токенов — консервативно. Если пользователь столкнётся с context errors — либо снизить `HISTORY_MAX_CHARS`, либо в будущем добавить tokenizer-based лимит (future task).
2. **System prompt не учитывается в лимите** — char-trim смотрит только на history. System prompt (~70 chars) prepend-ится отдельно в handlers.py. Незначительно на фоне 8000.
3. **Лог при trim** — нужно ли? Решение: да, structlog `history_char_trimmed` с полями `user_id`, `dropped_count`, `remaining_chars`. Помогает diagnostic'у.

---

## Pending action items

- [ ] **A1**: Создать ветку `feature/BAU/BOT-D05` (решить: от master после merge D-04, или от D-04 как dependent branch)
- [ ] **A2**: Реализовать char-trim в HistoryStore TDD-циклом · verify: 4 новых теста green
- [ ] **A3**: Обновить config + .env.example + main.py wiring
- [ ] **A4**: Ручная верификация в Telegram с длинным сообщением
- [ ] **A5**: Обновить docs (architecture edge case, context-dump Flow 2 шаг trim, tech-stack env)
- [ ] **A6**: Merge в master

---

## Regression watch

- Существующие 8 тестов HistoryStore должны остаться зелёными (gate на обратную совместимость `max_chars=0` default)
- Flow 2 в `context-dump.md` не меняется структурно — только упоминание, что trim теперь двухступенчатый
- `handlers.py` не меняется

---

## Dependencies

- D-04 должен быть merged (или branch должен быть dependent). Иначе HistoryStore ещё не существует.

---

## Links

- [change-request.md](../change-request.md) — live tracker (блок D-05)
- D-04 spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](D-04_DIALOG_HISTORY_YAML.md) — базовая инфра
- D-04 plan: [tasks/D-04_DIALOG_HISTORY_YAML_plan.md](D-04_DIALOG_HISTORY_YAML_plan.md)

---

## History

- 2026-04-15 — task started, design written, variant B (char limit as second safeguard on top of D-04 count limit) selected
