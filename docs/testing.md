# Testing

## Framework

- **pytest** 8.3.4
- **pytest-asyncio** 0.25.0 (для async-тестов)

## Запуск

```bash
make test                       # python3 -m pytest tests/ -v
python3 -m pytest tests/ -v     # прямой вызов
python3 -m pytest tests/test_llm_client.py::test_chat_success -v
```

## Структура

```
tests/
├── __init__.py
├── conftest.py
└── test_llm_client.py          — тесты LLMClient
```

Покрытие — точечное, на критические участки. BotHandlers **не покрыт тестами** (см. [tasks.md C-01 — Phase 3 tests](tasks.md)).

## Конфигурация

`conftest.py` — общие фикстуры.

Async-режим: `pytest-asyncio` в режиме `auto` — см. фактический `pyproject.toml` / `conftest.py`.

## Fixtures

### `llm` ([tests/test_llm_client.py:10-14](../tests/test_llm_client.py))
```python
@pytest_asyncio.fixture
async def llm():
    client = LLMClient()
    yield client
    await client.close()
```

Создаёт реальный `LLMClient` (httpx client под капотом моксится через `patch.object`).

## Паттерны моков

### Mock HTTP ответов
```python
with patch.object(llm._client, "post", new_callable=AsyncMock, return_value=mock_response):
    result = await llm.chat([...], model="test")
```

### Mock exceptions
```python
with patch.object(llm._client, "post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
    with pytest.raises(LLMError, match="timed out"):
        await llm.chat([...])
```

## Что покрыто

- `test_chat_success` — happy path, парсинг content и tokens_used
- `test_chat_timeout` — `httpx.TimeoutException` → `LLMError`
- `test_chat_connection_error` — `httpx.ConnectError` → `LLMError`

## Что НЕ покрыто (gaps)

- `LLMClient.list_models()` — happy + fallback на `AVAILABLE_MODELS`
- `LLMClient.chat()` — HTTP errors (`HTTPStatusError`), parse errors (`KeyError`/`IndexError`)
- `BotHandlers.handle_message` — happy path + error routing
- `BotHandlers.model_callback` — inline keyboard rebuild
- `BotHandlers.set_model` — валидация модели
- `BotHandlers._get_model` — возврат default и сохранённого
- `LoggingMiddleware.check_update` — сам факт что `return False`
- `setup_logging` — идемпотентность

## TDD mandatory

Все новые задачи следуют TDD:
1. **RED** — падающий тест
2. **GREEN** — минимальный код
3. **REFACTOR**

Подробнее: [instructions.md § 4](instructions.md#4-tdd--mandatory).

## Интеграционные / e2e

Нет. Для e2e нужно запускать реальный бот + реальный Lemonade + отправлять реальные сообщения через Telegram API (либо mock-telegram). Не окупается для текущего scope.
