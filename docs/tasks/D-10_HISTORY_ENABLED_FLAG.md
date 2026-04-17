# D-10 · HISTORY_ENABLED flag — выключаемый контекст одной env-переменной

| Поле | Значение |
|------|----------|
| **Task ID** | D-10 |
| **Ticket** | BOT-D10 |
| **Branch** | `feature/BAU/BOT-D10` |
| **Status** | Code complete, awaiting merge |
| **Owner** | Stan |
| **Started** | 2026-04-17 |

---

## Summary

До D-10 в `HistoryStore` все три лимита (`HISTORY_MAX_MESSAGES`, `HISTORY_MAX_CHARS`, `HISTORY_SUMMARIZE_THRESHOLD`) использовали семантику «0 = без лимита». Эта семантика правильная для лимитов, но **не даёт** возможности выключить историю целиком — установка всех трёх в 0 даёт **бесконечную память**, что противоположно «stateless».

D-10 вводит отдельный флаг `HISTORY_ENABLED` (default `true`), пробрасывает через config в `HistoryStore`, и когда `False`: `get()` → `[]`, `append()` → no-op, `replace()` → no-op (для полноты — summarizer не триггерится на пустой истории всё равно). `reset()` продолжает чистить старые файлы (user-facing cleanup).

## Motivation

Задача «как включить/выключить контекст» всплыла во время смоук-теста 2026-04-17. Раньше я ошибочно советовал ставить три лимита = 0 — это давало противоположный эффект. Правильное решение — explicit флаг.

---

## Design

### HistoryStore signature

```python
def __init__(
    self,
    data_dir: Path,
    max_messages: int,
    max_chars: int = 0,
    enabled: bool = True,    # NEW — default preserves backwards compat
) -> None:
```

### Behaviour gate

```python
async def get(self, user_id):
    if not self._enabled:
        return []
    # ... load+return as before

async def append(self, user_id, role, content):
    if not self._enabled:
        return
    # ... persist as before

async def replace(self, user_id, new_history):
    if not self._enabled:
        return
    # ... atomic overwrite
```

`reset()` **не gated** — пользователь может явно удалить существующие файлы (cleanup), даже когда feature disabled.

`mkdir(parents=True, exist_ok=True)` в `__init__` также gated — не создаём пустую `data/history/` когда disabled.

### Config + env

```python
# app/config.py
history_enabled: bool = True
```

```
# .env.example
# Enable dialog history (false = stateless, every message independent, /reset a no-op)
HISTORY_ENABLED=true
```

### Wiring в main.py

```python
history = HistoryStore(
    data_dir=Path(settings.history_dir),
    max_messages=settings.history_max_messages,
    max_chars=settings.history_max_chars,
    enabled=settings.history_enabled,
)
```

`starting_bot` log включает `history_enabled` для operational visibility.

### Взаимодействие с Summarizer

Когда `enabled=False`:
- `handle_message` получает `history_msgs = []` от `history.get()`
- `summarizer.maybe_summarize([])` возвращает `[]` (длина 0 ≤ threshold — триггер не срабатывает)
- `history.replace([])` был бы no-op, но и не вызывается
- `history.append()` is no-op после успешного ответа
- LLM payload: `[{system prompt}, {user text}]` — как в оригинальном MVP

Bot поведение identical stateless D-04 MVP.

---

## Success criteria

- [x] `settings.history_enabled` (default `true`) via env `HISTORY_ENABLED`
- [x] `HistoryStore.__init__` принимает `enabled` kwarg (default `True`), gated mkdir
- [x] `get()` / `append()` / `replace()` gated by `self._enabled`
- [x] 2 новых unit теста зелёные: `test_disabled_store_get_returns_empty`, `test_disabled_store_preserves_existing_file`
- [x] Существующие 27 тестов не сломаны — всего 29 зелёные
- [x] `make lint` чистый
- [x] main.py wiring; `starting_bot` log содержит `history_enabled`
- [ ] Ручной smoke: `HISTORY_ENABLED=false` + `make restart` → бот забывает контекст между сообщениями (проверь в Telegram после rebuild)
- [ ] Merge в master + push

---

## Scope

### In scope
- `app/history/store.py` — `enabled` kwarg + gates
- `app/config.py` — `history_enabled` field
- `app/main.py` — wiring + log field
- `.env.example` — env + объяснение
- `tests/test_history_store.py` — 2 unit теста
- Docs: architecture § 1, tech-stack env

### Out of scope
- Per-user toggle команды (например, `/stateless`) — общий флаг на весь инстанс достаточно
- Миграция существующих `data/history/*.yaml` — файлы остаются, просто игнорируются при disabled
- Автоматическое удаление файлов при disabled — явно не чистим, пользователь может руками удалить / использовать `/reset`

---

## Uncertainty list

1. **Race при смене enabled → disabled → enabled** — между рестартами; в памяти `_cache` пустой, диск читается заново. Не проблема.
2. **`/reset` при disabled** — продолжает удалять файл (user-facing команда должна работать). Наш reset не gated.

---

## Regression watch

- Старые HistoryStore вызовы `HistoryStore(data_dir, max_messages=N)` и `HistoryStore(data_dir, max_messages=N, max_chars=M)` продолжают работать — `enabled=True` default
- 27 существующих тестов используют default (enabled) — должны пройти без правок
- Bot поведение при `enabled=True` идентично D-09

---

## History

- 2026-04-17 — task started после discovery что «3 лимита в 0» ≠ stateless
- 2026-04-17 — implementation: 3 файла + 2 теста, 29/29 tests green, ruff clean
