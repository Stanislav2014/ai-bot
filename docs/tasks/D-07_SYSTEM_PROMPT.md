# D-07 · System prompt — configurable persona

| Поле | Значение |
|------|----------|
| **Task ID** | D-07 |
| **Ticket** | BOT-D07 |
| **Branch** | `feature/BAU/BOT-D07` (от master после D-04/D-05/D-06 merge) |
| **Status** | In Progress — Phase 0 |
| **Owner** | Stan |
| **Started** | 2026-04-15 |

---

## Summary

Сделать system prompt configurable через env `SYSTEM_PROMPT`. Заменить module-level константу `SYSTEM_PROMPT` в `handlers.py` на injected атрибут `BotHandlers.system_prompt`. Дефолт — русский программистский persona.

## Motivation

System prompt уже добавляется в LLM payload в `handle_message` (Flow 2 шаг 7). Но:
- текст захардкожен → нельзя поменять без пересборки
- дефолт — generic английский `"You are a helpful assistant..."` — не задаёт персоны

Задача — превратить в настоящий configurable paramaeter с осмысленным дефолтом.

---

## Design

### Config (`app/config.py`)

```python
system_prompt: str = "Ты опытный программист и отвечаешь кратко и по делу."
```

### `.env.example`

```
# System prompt — defines the bot persona (prepended to every LLM request)
SYSTEM_PROMPT=Ты опытный программист и отвечаешь кратко и по делу.
```

### `app/bot/handlers.py` — injection

Убрать module-level `SYSTEM_PROMPT` константу. Принять через `__init__`:

```python
class BotHandlers:
    def __init__(
        self,
        llm: LLMClient,
        history: HistoryStore,
        summarizer: Summarizer,
        system_prompt: str,
    ) -> None:
        self.llm = llm
        self.history = history
        self.summarizer = summarizer
        self.system_prompt = system_prompt
        self.user_models: dict[int, str] = {}
```

В `handle_message` использовать `self.system_prompt`:
```python
messages = (
    [{"role": "system", "content": self.system_prompt}]
    + history_msgs
    + [{"role": "user", "content": text}]
)
```

### `app/main.py` — wiring

```python
handlers = BotHandlers(
    llm=llm,
    history=history,
    summarizer=summarizer,
    system_prompt=settings.system_prompt,
)
```

В `starting_bot` лог добавить truncated prompt (первые 80 chars для операционной видимости, но не засорять логи):
```python
logger.info(
    "starting_bot",
    ...
    system_prompt=settings.system_prompt[:80],
)
```

### Summarizer — не трогаем

У `Summarizer` свой отдельный prompt (`SUMMARY_PROMPT` в `summarizer.py`) — это **инструкция для задачи суммаризации**, не persona бота. D-07 меняет только prompt основного диалога.

---

## Success criteria

- [ ] `settings.system_prompt` доступен через env `SYSTEM_PROMPT` (дефолт = русский программистский)
- [ ] `BotHandlers` принимает `system_prompt` через `__init__`
- [ ] Module-level `SYSTEM_PROMPT` константа удалена из handlers.py
- [ ] `handle_message` использует `self.system_prompt`
- [ ] main.py wiring; `starting_bot` лог содержит truncated system_prompt
- [ ] `.env.example` содержит `SYSTEM_PROMPT=` с комментарием
- [ ] Существующие 24 тестов не сломаны
- [ ] `make lint` чистый
- [ ] Ручной smoke: отправить «Что такое Python?» → ответ должен звучать как «опытный программист кратко и по делу» (короткий, точный, программистский тон)
- [ ] Попробовать override: `SYSTEM_PROMPT="Ты пират и отвечаешь как на корабле"` → ответы меняют стиль
- [ ] Merge в master

---

## Scope

### In scope
- `app/config.py` — поле `system_prompt`
- `app/bot/handlers.py` — инъекция + замена использования
- `app/main.py` — wiring
- `.env.example` — `SYSTEM_PROMPT` с русским дефолтом
- Docs: architecture (паттерн 1), context-dump Flow 2 step 7, tech-stack env

### Out of scope
- Per-user override (команда `/prompt`) — вариант B из брейнсторма, отдельная task если понадобится
- Persona packs / presets — вариант C
- Изменение `Summarizer` internal prompt — у него своя задача
- Unit-тесты handlers — handlers не покрываются в проекте (смотри [testing.md](../testing.md))

---

## Uncertainty list

1. **Encoding env**: русский текст в `.env` через pydantic-settings — работает без ритуалов, т.к. `env_file_encoding = "utf-8"` уже выставлен. Риска нет.
2. **Длинный prompt в логе** — truncate первыми 80 chars. Полный виден через `cat .env`.
3. **Кавычки в env значении** — если пользователь добавит `"` или `\n` в `.env`, pydantic-settings парсит dotenv-style. Для русской фразы без спецсимволов — нормально.
4. **Отсутствие handlers unit-тестов** — не блокер. Положимся на smoke.

---

## TDD phases

### Phase 0 — Research / Design ✅
- [x] Brainstorming, вариант A (env-configurable с русским дефолтом) утверждён
- [x] Spec записан
- [ ] Plan записан

### Phase 1 — Config + .env.example
- [ ] `app/config.py` — `system_prompt` с дефолтом
- [ ] `.env.example` — env переменная с комментарием

### Phase 2 — Refactor handlers.py
- [ ] Добавить `system_prompt` kwarg в `BotHandlers.__init__`
- [ ] Заменить `SYSTEM_PROMPT` константу на `self.system_prompt` в `handle_message`
- [ ] Удалить module-level `SYSTEM_PROMPT`

### Phase 3 — main.py wiring
- [ ] Передать `settings.system_prompt` в `BotHandlers`
- [ ] Добавить truncated `system_prompt` в `starting_bot` лог

### Phase 4 — Lint + tests
- [ ] `make lint` чистый
- [ ] `make test` — 24 теста зелёные (никаких регрессий)

### Phase 5 — Manual verification
- [ ] `make build && make restart`
- [ ] В Telegram: `/reset`, затем вопрос «Что такое Python?» — ответ в программистском тоне
- [ ] Попробовать override через `.env` (поменять на «пирата»), `make restart`, проверить что стиль меняется

### Phase 6 — Docs update
- [ ] `architecture.md` § 1 — уточнение что system prompt теперь configurable
- [ ] `context-dump.md` Flow 2 step 7 — ссылка на `settings.system_prompt`
- [ ] `tech-stack.md` env table — `SYSTEM_PROMPT` строка
- [ ] `tasks.md` — D-07 ✅
- [ ] `current-sprint.md` — D-07 Done
- [ ] `change-request.md` — D-07 блок обновить статусом Merged

---

## Regression watch

- `handle_message` единственная точка использования system prompt — риск минимальный
- Существующие 24 теста не трогают handlers.py напрямую, должны остаться зелёными
- `Summarizer` изолирован — D-07 на него не влияет

---

## Links

- D-04 spec: [tasks/D-04_DIALOG_HISTORY_YAML.md](D-04_DIALOG_HISTORY_YAML.md) — первичный mechanism prepend system_prompt
- [architecture.md § 1](../architecture.md) — будет обновлён
- [context-dump.md Flow 2](../context-dump.md) — будет обновлён

---

## History

- 2026-04-15 — task started, brainstorming done, вариант A утверждён (env-configurable, русский дефолт)
