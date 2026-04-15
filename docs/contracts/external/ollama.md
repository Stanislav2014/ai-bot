# Ollama / Lemonade — OpenAI-compatible API

**Direction**: исходящие HTTP

**Protocol**: HTTP (OpenAI-compatible)

**SDK / library**: нет SDK — `httpx.AsyncClient` напрямую

⚠ Проект написан против OpenAI-compatible API, поэтому совместим с любым сервером, реализующим `/v1/chat/completions` и `/v1/models`: **Ollama**, **Lemonade**, **vLLM**, **LM Studio**, **localai**.

## Use cases

| Операция | Endpoint | Метод | Где в коде |
|----------|----------|-------|-----------|
| Chat completion | `/v1/chat/completions` | POST | [app/llm/client.py:28-45](../../../app/llm/client.py) `LLMClient.chat()` |
| List models | `/v1/models` | GET | [app/llm/client.py:60-70](../../../app/llm/client.py) `LLMClient.list_models()` |

## Request schema

### `POST /v1/chat/completions`
```json
{
  "model": "qwen3:0.6b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant. Answer concisely and accurately."},
    {"role": "user", "content": "<user text>"}
  ],
  "stream": false
}
```

### Response
```json
{
  "choices": [
    {"message": {"content": "<LLM answer>"}}
  ],
  "usage": {
    "total_tokens": 123
  }
}
```

Код читает:
- `data["choices"][0]["message"]["content"]` — текст ответа (required)
- `data.get("usage", {}).get("total_tokens")` — опционально, для логов

### `GET /v1/models`
Response:
```json
{
  "data": [
    {"id": "qwen3:0.6b"},
    {"id": "qwen3:1.7b"}
  ]
}
```

Код читает `[m["id"] for m in data.get("data", [])]`.

## Configuration

| Env | Default | Назначение |
|-----|---------|-----------|
| `LLM_BASE_URL` | `http://ollama:11434` (⚠ в коде) / `http://lemonade:8000/api` (в .env.example) | Base URL OpenAI-compatible сервера |
| `DEFAULT_MODEL` | `qwen3:0.6b` | Модель по умолчанию, если юзер не переключил |
| `LLM_TIMEOUT` | 120 | HTTP timeout в секундах для chat запросов |

⚠ **Несогласованность**: default в `app/config.py` ≠ `.env.example`. См. [legacy-warning.md § 1](../../legacy-warning.md#1-ollama--lemonade-несогласованность).

## Auth

Нет. Локальный сервер в той же Docker сети. Если когда-нибудь деплоить на публичный LLM сервер — нужен API ключ в Authorization header.

## Обрабатываемые ошибки

| Ошибка | Маппинг |
|--------|---------|
| `httpx.TimeoutException` | `LLMError("LLM request timed out after {N}s")` |
| `httpx.HTTPStatusError` (4xx/5xx) | `LLMError("LLM returned HTTP {code}")` |
| `httpx.ConnectError` | `LLMError("Cannot connect to LLM server. Is Ollama running?")` |
| `KeyError`/`IndexError` при парсинге | `LLMError("Failed to parse LLM response")` |

`list_models()` — `except Exception` → fallback на хардкод `AVAILABLE_MODELS`. См. [legacy-warning.md § 3](../../legacy-warning.md#3-list_models-fallback-вводит-в-заблуждение).

## Gotchas

- **Streaming не используется** — `"stream": false` жёстко зашит. Для простоты логирования. См. [ideas.md](../../ideas.md).
- **Cold start** — первый запрос к Lemonade после старта может занять много секунд (загрузка модели в память). `LLM_TIMEOUT=120` это покрывает.
- **404 на модель** — если `model` name неверный, сервер возвращает 404. Хэндлер преобразует в user-friendly «Model not available» ([app/bot/handlers.py:144-147](../../../app/bot/handlers.py)).
- **`/v1/models` доступен не у всех серверов** — некоторые реализации отвечают 400/404. Код fallback-ит (см. legacy-warning § 3).
- **`total_tokens` может отсутствовать** — не все серверы возвращают `usage`. Код это учитывает через `.get()`.
- **URL строится с `rstrip("/")`** — чтобы не получать `//v1/...` при trailing slash в env.

## Related code

- [app/llm/client.py](../../../app/llm/client.py) — весь HTTP-слой
- [app/config.py](../../../app/config.py) — env parsing
- [tests/test_llm_client.py](../../../tests/test_llm_client.py) — тесты (happy + timeout + connect error)

## Migration notes (Ollama → Lemonade)

- docker-compose уже переключён на `lemonade` сервис
- `.env.example` указывает на lemonade:8000/api
- Но `app/config.py` и `README.md` упоминают Ollama — миграция не закончена
- См. [plan.md § Фаза 2](../../plan.md#фаза-2--migration-to-lemonade)

## History

- 2026-04-09 — старт с Ollama
- 2026-04-10 — docker-compose переключён на Lemonade (частичная миграция)
