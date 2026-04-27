# I-01 · CI/CD pipeline через GitHub Actions

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `I-01` (новая фаза `I-` — Infrastructure / DevOps) |
| **Ticket** | — (homework) |
| **Branch** | `feature/CI/I-01-github-actions` |
| **Started** | 2026-04-27 |
| **Status** | In Review |
| **Owner** | Stan |

---

## Goal

Любое изменение в боте автоматически проверяется CI до merge: lint + tests. Pipeline быстрый, изолированный (без сети к Telegram/Lemonade), падает при ошибках. Бонус — feature flag `LLM_ENABLED` для маинтенанса/cost-control.

## Success criteria

- [x] **CR-1**: `.github/workflows/ci.yml` создан, валидный YAML
- [x] **CR-2**: Pipeline триггерится на `push: master` и `pull_request → master`
- [x] **CR-3**: Pipeline ставит Python 3.12, кеширует `pip` зависимости (по `requirements-dev.txt` hash)
- [x] **CR-4**: Pipeline запускает `python -m ruff check app/ tests/` (lint) и `python -m pytest tests/ -v` (test)
- [x] **CR-5**: Тесты не лезут в сеть — fake токены через env (`TELEGRAM_BOT_TOKEN=dummy`, `LLM_BASE_URL=localhost:9999`); `conftest.py` уже ставит defaults через `setdefault`, CI vars — belt-and-braces
- [x] **CR-6**: Никаких реальных секретов в репозитории (`.env` в `.gitignore`, в workflow только dummy)
- [x] **CR-7 (бонус)**: Feature flag `LLM_ENABLED` — когда `false`, `ChatService.reply` возвращает canned reply (`LLM_DISABLED_REPLY`) без вызова LLM и без публикации событий
- [x] **CR-8**: 72/72 tests green локально (3 новых теста на feature flag)
- [ ] **CR-9**: первый run на GitHub Actions зелёный (verify после push ветки)

---

## Scope

### In scope
- `.github/workflows/ci.yml` — single job `Tests + Lint`
- Feature flag `LLM_ENABLED` + `LLM_DISABLED_REPLY` в `app/config.py`, прокидывается через `main.py` в `ChatService`
- 3 новых теста: canned reply / no LLM call / no events
- Update `.env.example`
- Документация: `tasks.md`, `change-request.md`, `current-sprint.md`

### Out of scope
- Coverage reporting (можно добавить в I-02)
- Автодеплой / docker push (нет prod-сервера)
- Matrix testing на разных Python (3.11/3.12) — пока хватает 3.12
- mypy / pyright type-check (не настроен в проекте)
- Pre-commit hooks
- Notifications (Slack/email)

---

## Impact

### Новые файлы
| Файл | Назначение |
|------|------------|
| `.github/workflows/ci.yml` | Single job: Python 3.12 → install → lint → test |
| `docs/tasks/I-01_GITHUB_ACTIONS.md` | этот файл |

### Изменяемые файлы
| Файл | Характер |
|------|----------|
| `app/config.py` | +`llm_enabled: bool = True`, +`llm_disabled_reply: str` |
| `app/chat/service.py` | `ChatService.__init__` принимает `llm_enabled` + `llm_disabled_reply`; `reply()` возвращает canned reply если flag false (early return — без модели, истории, событий) |
| `app/main.py` | Передаёт `settings.llm_enabled` + `settings.llm_disabled_reply` в `ChatService` |
| `tests/test_chat_service.py` | +3 теста на feature flag |
| `.env.example` | Документировать `LLM_ENABLED` + `LLM_DISABLED_REPLY` |
| `docs/tasks.md`, `current-sprint.md`, `change-request.md` | блок I-01 |

---

## Pipeline structure

```yaml
on:
  push:    branches: [master]
  pull_request:  branches: [master]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - actions/checkout@v4
      - actions/setup-python@v5 (3.12 + pip cache)
      - install requirements-dev.txt
      - lint:  python -m ruff check app/ tests/
      - test:  python -m pytest tests/ -v   # с fake env vars
```

**Ожидаемое время run:** ~30-60s (cache hit) / ~1-2 min (cache miss). Тесты сами ~1s, остальное — setup.

**Изоляция:** ни один тест не делает реальные HTTP/Telegram-вызовы. `LLMClient` мокается через `AsyncMock` в `test_chat_service.py`. `HistoryStore` / `UserStore` пишут в `tmp_path`. `EventBus` — in-memory.

---

## Feature flag (бонус)

```python
# app/config.py
llm_enabled: bool = True
llm_disabled_reply: str = "🛠 AI временно отключён..."

# app/chat/service.py
async def reply(self, telegram_id, text):
    if not self._llm_enabled:
        logger.info("llm_disabled_reply", user_id=telegram_id, text_length=len(text))
        return self._llm_disabled_reply
    # ... обычный flow
```

**Когда полезно:**
- Maintenance window — выключаешь LLM, бот вежливо отвечает
- Cost control — если Lemonade платный (мы local, но pattern переиспользуемый)
- Тестирование транспорта без LLM
- Аварийный fallback — по cron'у проверяешь Lemonade health, при failure → flip env + restart

**Решения:**
- Когда disabled — НЕ публикуем `MessageReceived` / `ResponseGenerated` (диалог фактически не состоялся; пишем только лог `llm_disabled_reply`). Иначе history засорится фейковыми "AI отключён" ответами
- Логируем `llm_disabled_reply` чтобы оператор видел сколько сообщений отбито

---

## Verify plan

1. Локально: `make test` → 72/72, `make lint` → clean ✅
2. После push ветки → GitHub Actions автоматически запустит CI
3. Если зелёный → CR-9 ✅, мержим
4. Если красный → анализ через `gh run list` / `gh run view`, fix, push снова

---

## History
- 2026-04-27 — спека + ветка
- 2026-04-27 — `.github/workflows/ci.yml` написан, локально валидирован YAML, тесты 69→72 green
- 2026-04-27 — Feature flag `LLM_ENABLED` реализован (бонус); 3 теста добавлены
