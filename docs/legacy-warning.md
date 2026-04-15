# Legacy Warning — тех-долг / костыли / known issues

Каталог известных проблем и компромиссов. Приоритеты:
- 🔥 **Критичное** — мешает работе / опасно для прода
- ⚠ **Архитектурное** — не блокирует, но требует внимания при расширении
- 🧟 **Стилистическое / cosmetic** — не срочно, но раздражает

---

## 1. Ollama ↔ Lemonade несогласованность
⚠ Архитектурное

**Что**: В разных местах проекта упоминаются два разных LLM сервера.

| Место | Значение |
|-------|----------|
| `app/config.py:6` — `llm_base_url` default | `http://ollama:11434` |
| `.env.example:5` — `LLM_BASE_URL` | `http://lemonade:8000/api` |
| `docker-compose.yml` — сервис | `lemonade` |
| `README.md` | Упоминает Ollama + `ollama serve` |
| `Makefile:31-32` — `pull-models` | `docker compose exec ollama ollama pull` |

**Почему**: Миграция Ollama → Lemonade начата (docker-compose уже на Lemonade), но не доведена.

**Риск**: Новый клон репо без `.env` → подхватит Python default `http://ollama:11434` → `ConnectError`. Команда `make pull-models` сломана (нет сервиса `ollama`).

**Fix**: Либо финализировать миграцию на Lemonade (C-01 + C-02), либо откатить docker-compose.

**Связанные задачи**: [tasks.md C-01, C-02](tasks.md#phase-c--технический-долг).

---

## 2. Makefile `pull-models` сломан
🔥 Критичное (для onboarding)

**Что**: [Makefile:31-32](../Makefile)
```makefile
pull-models:
	docker compose exec ollama ollama pull qwen3:0.6b
	docker compose exec ollama ollama pull qwen3:1.7b
```

Сервис `ollama` в `docker-compose.yml` отсутствует — есть только `lemonade`. Команда завершится ошибкой «no such service».

**Fix**: Переписать под Lemonade (если Lemonade поддерживает pull через exec) или удалить, указав что модели грузятся через volume / Dockerfile / startup script.

**Связанные задачи**: [tasks.md C-02](tasks.md#phase-c--технический-долг).

---

## 3. `list_models()` fallback вводит в заблуждение
⚠ Архитектурное

**Где**: [app/llm/client.py:60-70](../app/llm/client.py)

**Что**: При любой ошибке (`except Exception`) возвращается хардкод-список:
```python
AVAILABLE_MODELS = ["gpt-oss-20b", "qwen3:0.6b", "qwen3.5:27b"]
```

**Проблема**: Если LLM сервер не поддерживает `/v1/models` или отдаёт 5xx, пользователь увидит в `/models` эти три модели — даже если их там на самом деле нет. Переключение покажет «Switched», а при первом реальном запросе → 404.

**Fix**:
- Либо показывать пользователю сообщение «не удалось получить список — попробуйте позже»
- Либо делать fallback только при `404` на `/v1/models` (endpoint отсутствует), а прочие ошибки пропускать наверх

---

## 4. `user_models` — per-user модель в памяти процесса
⚠ Архитектурное (by design, но только для выбора модели — история диалога персистентна, см. D-04)

**Где**: [app/bot/handlers.py](../app/bot/handlers.py) — `self.user_models: dict[int, str] = {}`

**Что**: Выбранная модель per-user живёт только в памяти процесса. При рестарте все выбранные сбрасываются на `settings.default_model`. История диалога при этом сохраняется (реализовано в D-04).

**Fix**: см. [discuss.md § 1](discuss.md#1-persistence-для-per-user-selected-model). Следующий шаг — D-03 (persistent user_models).

---

## 5. `list_models()` вызывается multiple раз per action
🧟 Стилистическое

**Где**: [app/bot/handlers.py](../app/bot/handlers.py) — в `models()`, `model_callback()`, `set_model()`.

**Что**: Каждый раз — свежий HTTP GET к LLM серверу. При спам-нажатиях inline buttons — много запросов.

**Fix**: TTL-кеш на 60s. См. [tasks.md C-03](tasks.md#phase-c--технический-долг).

---

## 6. `LoggingMiddleware` — subclass `BaseHandler` с `return False`
🧟 Стилистическое / архитектурное

**Где**: [app/bot/middleware.py](../app/bot/middleware.py)

**Что**: Не настоящий middleware, а `BaseHandler` с `check_update` всегда возвращающий `False`, чтобы update прошёл дальше.

**Проблема**: Неочевидно для нового разработчика. Если кто-то по привычке поменяет `return False` на `return True` (или забудет) — все хэндлеры перестанут получать сообщения.

**Fix**: Использовать python-telegram-bot native error handlers или `TypeHandler` с правильным flow. Либо добавить комментарий-warning в коде прямо над `return False`.

---

## 7. Длинные LLM ответы > 4096 символов сломают `reply_text`
⚠ Архитектурное / потенциальный bug

**Где**: [app/bot/handlers.py:140](../app/bot/handlers.py)

**Что**: `update.message.reply_text(reply)` — без разбиения на части. Telegram API отвергает сообщения > 4096 символов.

**Риск**: На некоторых моделях (когда LLM «разговорится») — попадёт на `Exception` → пользователь увидит generic error.

**Fix**: Либо `textwrap`-разбиение на части, либо truncate с пометкой `... (truncated)`, либо оба варианта.

---

## 8. `httpx.AsyncClient` без явных лимитов pool
🧟 Стилистическое

**Где**: [app/llm/client.py:19](../app/llm/client.py)

**Что**: `self._client = httpx.AsyncClient(timeout=self.timeout)` — без `limits`.

**Проблема**: При multi-user нагрузке может быть connection saturation. Сейчас не актуально.

**Fix**: `httpx.Limits(max_connections=N, max_keepalive_connections=M)`.

---

## 9. Нет retry на транзиентные ошибки LLM
⚠ Архитектурное

**Что**: Любой `httpx.HTTPStatusError` / `TimeoutException` → сразу `LLMError` → сообщение пользователю.

**Проблема**: Транзиентные 5xx / короткие таймауты не ретраятся — UX страдает на cold-start LLM.

**Fix**: `tenacity` или самописный retry с backoff на 5xx/timeout для `chat()` (1-2 попытки). НЕ делать retry для 4xx.

---

## 10. `lemonade/` папка untracked в git
🧟 Стилистическое / процесс

**Что**: В `git status` висит untracked `lemonade/` (содержит Dockerfile). `docker-compose.yml` на неё ссылается через `build: ./lemonade`.

**Проблема**: У нового клонирующего проект — сборка упадёт (`lemonade/Dockerfile not found`).

**Fix**: Закоммитить `lemonade/Dockerfile` и всё что нужно для сборки.
