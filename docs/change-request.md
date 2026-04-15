# Change Request — текущий

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `D-04` |
| **Ticket** | `BOT-D04` (внутренний, без внешнего трекера) |
| **Branch** | `feature/BAU/BOT-D04` |
| **Task spec** | [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md) |
| **Started** | 2026-04-15 |
| **Status** | In Progress (Phase 0 — Research / Design) |
| **Owner** | Stan |

---

## Goal

Реализовать псевдо-память: хранить историю диалога `user`/`assistant` per-user в YAML-файле на диске, отправлять в LLM полную историю + новое сообщение при каждом запросе.

## Success criteria (verifiable)

- [ ] Пользователь пишет 2 сообщения подряд — второе сообщение LLM получает с контекстом первого → verify: ручной тест в Telegram + лог `llm_request` содержит `messages_count > 2`
- [ ] При рестарте бота история сохраняется → verify: ручной тест (отправить сообщение → `docker compose restart bot` → продолжить диалог) + файл `data/history/{user_id}.yaml` существует и содержит прошлые сообщения
- [ ] Два разных пользователя видят только свою историю → verify: `test_per_user_isolation` + ручной тест с двумя аккаунтами
- [ ] Команда `/reset` очищает историю → verify: `test_reset_clears_file` + ручной тест
- [ ] Window лимит работает: `HISTORY_MAX_MESSAGES=4` → не больше 4 сообщений в файле → verify: `test_window_trims_when_over_limit`
- [ ] `HISTORY_MAX_MESSAGES=0` = без лимита → verify: `test_window_zero_means_unlimited`
- [ ] Corrupt YAML файл не ломает бота → verify: `test_corrupt_yaml_recovers`
- [ ] `make test` зелёный · `make lint` зелёный

---

## Scope

### In scope
- Новый модуль `app/history/store.py` — `HistoryStore` класс
- Интеграция в `BotHandlers.handle_message`
- Новая команда `/reset`
- Env-переменные `HISTORY_DIR`, `HISTORY_MAX_MESSAGES`
- Зависимость `PyYAML`
- Тесты `tests/test_history_store.py`

### Out of scope
- Отдельное сохранение system prompt в файле (всегда prepend-им из кода)
- Persistent `user_models` dict (остаётся in-memory — отдельная задача D-03)
- Миграция existing пользователей (их нет или пустое состояние)
- Compression/archival старых историй
- Управление историей через команды (просмотр, удаление отдельных сообщений)

---

## Impact / change surface

### Изменяемые файлы
| Файл | Характер изменений |
|------|--------------------|
| `app/history/__init__.py` | NEW — экспорт `HistoryStore` |
| `app/history/store.py` | NEW — `HistoryStore` класс |
| `app/bot/handlers.py` | Инъекция `history` в `__init__`, изменения в `handle_message`, новый `reset` |
| `app/main.py` | Инстанцирование `HistoryStore`, передача в `BotHandlers`, регистрация `CommandHandler("reset")` |
| `app/config.py` | Добавить `history_dir`, `history_max_messages` |
| `requirements.txt` | + `PyYAML==6.0.2` |
| `.env.example` | + `HISTORY_DIR`, `HISTORY_MAX_MESSAGES` |
| `tests/test_history_store.py` | NEW — 8 тестов (см. ниже) |

### Затронутые потоки (из [context-dump.md](context-dump.md))
- **Flow 2 — Incoming text message (happy path)**: добавляются шаги load history перед LLM запросом и append после ответа
- **Flow 7 — `/start`/`/help`**: обновить текст помощи, добавить упоминание `/reset`
- **Новый Flow — `/reset`**: полностью новый

### Затронутые контракты
- **contracts/external/ollama.md** — размер `messages` массива растёт: теперь `[system] + history + [user]`. Риск: context-length exceeded на длинных историях (смягчается window limit).

---

## Uncertainty list

1. **Window FIFO по сообщениям или по парам?** Текущее решение: по сообщениям (проще). После обрезки первое сообщение может оказаться `assistant` — OpenAI-compatible серверы это принимают, но может ухудшить качество. Если окажется проблемой — переделать на обрезку по парам (`user`+`assistant` вместе).
2. **PyYAML performance** — `yaml.safe_load`/`yaml.safe_dump` на каждую операцию. Для десятков файлов по 20 сообщений это незначительно. Если когда-нибудь станет боттлнеком — переключиться на `ruamel.yaml` или JSON.
3. **`user_id` как имя файла** — `int` → `f"{user_id}.yaml"`. Telegram user_id это int64, безопасно для имени файла. Не нужен escape.
4. **Async file I/O** — использовать `asyncio.to_thread(open, ...)` чтобы не блокировать event loop? Файлы маленькие, sync `open` + `yaml.safe_load` займёт <1ms. Решение: sync внутри async метода, без `to_thread`. Если профайлер покажет блокировки — добавим.
5. **Локи per user** — `dict[int, asyncio.Lock]`. Очищать ли их когда-нибудь? Для bot-а с десятками активных пользователей это мизерная утечка (dict никогда не превысит числа юзеров). Решение: не чистить.

---

## Pending action items

- [ ] **A1**: Создать `app/history/` модуль с `HistoryStore` · verify: `pytest tests/test_history_store.py -v` зелёный · owner: Stan
- [ ] **A2**: Интегрировать `HistoryStore` в `handle_message` (TDD) · verify: ручной тест 2 сообщений в Telegram, проверка лога `llm_request` · owner: Stan
- [ ] **A3**: Команда `/reset` + регистрация в `main.py` · verify: ручной тест · owner: Stan
- [ ] **A4**: Config + .env.example · verify: `settings.history_dir`, `settings.history_max_messages` работают · owner: Stan
- [ ] **A5**: Обновить тексты `/start` и `/help` · verify: вручную в Telegram · owner: Stan
- [ ] **A6**: Обновить docs (Flow 2 в context-dump, discuss § 2, legacy-warning, db-schema, architecture, ui-kit, tech-stack, tasks.md) · verify: grep по упомянутым файлам показывает обновлённый текст · owner: Stan

---

## TDD phases

### Phase 0 — Research / Design
- [x] Brainstorming (выбран variant B — persistent YAML)
- [x] Дизайн утверждён
- [x] Spec записан в [tasks/D-04_DIALOG_HISTORY_YAML.md](tasks/D-04_DIALOG_HISTORY_YAML.md) (единственная точка истины для задачи)
- [ ] Implementation plan создан через writing-plans skill

### Phase 1 — HistoryStore module (TDD)
- [ ] RED: `test_get_empty_user` → нет файла, `get()` возвращает `[]`
- [ ] GREEN: минимальный `HistoryStore.get()` с проверкой существования файла
- [ ] RED: `test_append_and_get` → пара сообщений в правильном порядке
- [ ] GREEN: реализация `append()` с записью в YAML
- [ ] RED: `test_persistence_across_instances` → новый HistoryStore читает то же что написал старый
- [ ] GREEN: подтверждается (flush-ом/fsync — если нужно)
- [ ] RED: `test_window_trims_when_over_limit` (max=4)
- [ ] GREEN: реализация sliding window
- [ ] RED: `test_window_zero_means_unlimited` (max=0, append 50)
- [ ] GREEN: guard на `max > 0`
- [ ] RED: `test_reset_clears_file`
- [ ] GREEN: `reset()` удаляет файл и запись в кеше
- [ ] RED: `test_corrupt_yaml_recovers` → подложить битый файл, `get()` → `[]`
- [ ] GREEN: try/except при чтении + лог + перезапись пустым
- [ ] RED: `test_per_user_isolation` → разные user_id не перемешиваются
- [ ] GREEN: проверка изоляции
- [ ] REFACTOR: вынести пути, проверить типы, ruff

### Phase 2 — Config
- [ ] Добавить `history_dir`, `history_max_messages` в `app/config.py`
- [ ] Обновить `.env.example`

### Phase 3 — Handlers integration (TDD где возможно)
- [ ] Инъекция `history` в `BotHandlers.__init__`
- [ ] Изменения `handle_message` (load → build messages → append user → call LLM → append assistant)
- [ ] Новый `reset` handler
- [ ] Обновить тексты `/start` и `/help`

### Phase 4 — Wiring в main.py
- [ ] Инстанцировать `HistoryStore`
- [ ] Передать в `BotHandlers`
- [ ] Зарегистрировать `CommandHandler("reset")`

### Phase 5 — Manual testing
- [ ] Запустить бота, отправить 2 сообщения, проверить что второе понимает контекст
- [ ] Рестарт бота → история сохранилась
- [ ] `/reset` → история очищена, файл удалён
- [ ] Второй пользователь (другой аккаунт) не видит историю первого
- [ ] `make test` зелёный
- [ ] `make lint` зелёный

### Phase 6 — Docs update
- [ ] `context-dump.md` Flow 2 — новые шаги
- [ ] `context-dump.md` — новый Flow 9: `/reset`
- [ ] `discuss.md § 2` — решение принято
- [ ] `legacy-warning.md § 4` — сузить scope до `user_models` (история теперь персистентна)
- [ ] `db-schema.md` — YAML files per user в таблице «Что где хранится»
- [ ] `architecture.md` — новый паттерн «Per-user persistent history» + edge case concurrent writes
- [ ] `ui-kit.md` — добавить `/reset` в команды + тексты
- [ ] `tech-stack.md` — добавить `PyYAML==6.0.2`
- [ ] `tasks.md` — D-04 → ✅
- [ ] `current-sprint.md` — D-04 → Done

---

## Regression watch

- **Flow 2 изменён** — risk сломать существующее поведение «1 сообщение = 1 LLM запрос». Тесты `test_chat_*` в `tests/test_llm_client.py` должны остаться зелёными (LLMClient не трогаем).
- **Memory growth** — `_locks` dict в `HistoryStore` растёт. Для текущей нагрузки не актуально, но mention.
- **LLM context length** — длинные истории могут превысить context window модели. Window lim смягчает, но не полностью гарантирует. Риск: ошибка 400 от Lemonade на длинных диалогах.
- **`data/` volume в docker-compose** — сейчас НЕ проброшен наружу контейнера. При `docker compose down` → `up` история теряется. Нужно добавить volume для `data/` или обсудить.
- **Dockerfile perms** — `data/` создаётся через mkdir в Dockerfile, но `history/` поддиректория создаётся программно под `botuser` — должно работать.

---

## Checkpoints

### Phase 0 checkpoint
Дизайн утверждён (2026-04-15). Вариант B выбран (YAML per-user, default window 20, `/reset` команда). Далее — spec.md + plan.md.

---

## History

- 2026-04-15 — task started, brainstorming done, variant B selected
