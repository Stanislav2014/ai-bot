# D-08 · Context logging — full payload visibility перед LLM call

| Поле | Значение |
|------|----------|
| **Task ID** | D-08 |
| **Ticket** | BOT-D08 |
| **Branch** | `feature/BAU/BOT-D08` |
| **Status** | ✅ Merged 2026-04-15 · commits `7adcef1` + `605d59d` + `f130fb6` · verified in prod 2026-04-16 |
| **Owner** | Stan |
| **Started** | 2026-04-15 |

---

## Summary

Расширить existing log event `llm_request` в `LLMClient.chat()`:
- добавить `total_chars` (sum of content lengths)
- добавить `estimated_tokens` (`total_chars // 4` heuristic)
- добавить `messages` (полный payload, role+content) под гейтом env `LOG_CONTEXT_FULL` (default `true`)

Логирование происходит в `LLMClient.chat()`, что покрывает **оба** LLM-вызова: основной диалог `handle_message` и summarization `Summarizer._call_llm`.

## Motivation

Сейчас `llm_request` лог содержит только `model` и `messages_count`. Нельзя посмотреть, что именно ушло в модель — особенно полезно при debugging summarization (видно ли старая история в transcript-e), и при тестировании system prompt (работает ли override из env).

Task 5 из Sprint 1, спрошена 2026-04-15 (formulation: "обязательно" — то есть enabled by default).

---

## Design

### Helper function

```python
def _context_stats(messages: list[dict[str, str]]) -> tuple[int, int]:
    """Return (total_chars, estimated_tokens). Tokens = chars // 4 heuristic."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars, total_chars // 4
```

**Heuristic justification**: для смешанного русского/английского контента на qwen3 tokenizer даёт ~3-4 chars/token. `total_chars // 4` — консервативная оценка (недоцениваем, не переоцениваем лимит). Точный счёт потребовал бы tiktoken или model-specific tokenizer — не нужно для observability.

### `LLMClient.chat()` — log расширение

Текущий код:
```python
logger.info("llm_request", model=model, messages_count=len(messages))
```

Становится:
```python
total_chars, est_tokens = _context_stats(messages)
log_data: dict = {
    "model": model,
    "messages_count": len(messages),
    "total_chars": total_chars,
    "estimated_tokens": est_tokens,
}
if settings.log_context_full:
    log_data["messages"] = messages
logger.info("llm_request", **log_data)
```

### Config

```python
# app/config.py
log_context_full: bool = True
```

### .env.example

```
# Log full LLM context (messages with content) — disable in production if logs grow
LOG_CONTEXT_FULL=true
```

### Тесты

`tests/test_llm_client.py` расширяется одним unit тестом на helper:

```python
from app.llm.client import _context_stats


def test_context_stats_counts_chars_and_tokens() -> None:
    messages = [
        {"role": "system", "content": "Hi"},          # 2 chars
        {"role": "user", "content": "Hello world"},   # 11 chars
    ]
    total_chars, est_tokens = _context_stats(messages)
    assert total_chars == 13
    assert est_tokens == 3  # 13 // 4


def test_context_stats_empty_messages() -> None:
    assert _context_stats([]) == (0, 0)


def test_context_stats_ignores_missing_content_field() -> None:
    # Defensive: some messages may be malformed, shouldn't crash
    assert _context_stats([{"role": "system"}]) == (0, 0)
```

Существующие 3 теста LLMClient не ломаются (log-конфигурация — behind feature flag, default on, но они мокают `_client.post` — логирование до HTTP вызова).

---

## Success criteria

- [x] `_context_stats(messages)` helper работает, 3 unit теста зелёные · [app/llm/client.py:15-18](../../app/llm/client.py), [tests/test_llm_client.py](../../tests/test_llm_client.py)
- [x] `LLMClient.chat()` логирует `llm_request` с новыми полями (`total_chars`, `estimated_tokens`) всегда; `messages` — под env `LOG_CONTEXT_FULL` · [app/llm/client.py:41-50](../../app/llm/client.py)
- [x] `settings.log_context_full` env поле (default `true`) · [app/config.py](../../app/config.py)
- [x] `.env.example` описывает `LOG_CONTEXT_FULL` · [.env.example](../../.env.example)
- [x] Существующие тесты зелёные — всего 27 (3 LLM + 13 history + 8 summarizer + 3 context_stats)
- [x] `make lint` чистый
- [x] Ручной smoke: prod лог 2026-04-16 18:50:49 — `{"model":"Qwen3-8B-GGUF","messages_count":2,"total_chars":76,"estimated_tokens":19,"messages":[...],"event":"llm_request"}` — все поля видны для user диалога
- [x] Override `LOG_CONTEXT_FULL=false` → messages исчезают, metadata остаётся · verified 2026-04-16 19:00:31 (subprocess smoke): `llm_request estimated_tokens=4 messages_count=1 model=Qwen3-0.6B-GGUF total_chars=18` (без `messages`)
- [x] Merge в master · `7adcef1` feat, `605d59d` docs
- [ ] **(open)** Smoke для summarization вызова: триггер на 6-м сообщении в одной сессии — пока не воспроизведён, требуется реальный длинный диалог в Telegram

---

## Scope

### In scope
- `app/llm/client.py` — `_context_stats` helper + расширение `llm_request` лога
- `app/config.py` — `log_context_full`
- `.env.example` — env переменная
- `tests/test_llm_client.py` — 3 unit теста на helper
- Docs: architecture, context-dump Flow 2, tech-stack env

### Out of scope
- Точный tokenizer (tiktoken, hf tokenizers) — 5% улучшения точности не стоит +1 dep + возможный rebuild с rust toolchain
- Логирование в отдельный файл — structlog уже в stdout (JSON), `docker logs bot > file.log` если нужно
- Логирование LLM response (content + tokens_used) — уже есть event `llm_response`, достаточно
- Throttling/rate limiting логов — при нормальной нагрузке не проблема, если станет — отдельная задача

---

## Uncertainty list

1. **Heuristic accuracy** — `chars // 4` может недооценить/переоценить на 30% для специфичного контента. Приемлемо для observability — цель «видеть масштаб», не biller-grade precision.
2. **Log size growth** — при `LOG_CONTEXT_FULL=true` каждый LLM-запрос логирует весь context (может быть 8000 chars). Docker log rotation по дефолту держит 10MB × 3 файла — хватит на тысячи сообщений. В проде при больших нагрузках — отключить.
3. **Security** — `messages` может содержать персональные данные пользователей. Логи остаются на хосте (docker-logs), доступ контролируется filesystem perms. Для публичного развёртывания — отключить через `LOG_CONTEXT_FULL=false`.

---

## TDD phases

### Phase 0 — Design ✅
- [x] Дизайн утверждён (вариант A: уровень LLMClient, env gate для full content)
- [x] Spec записан (этот файл)

### Phase 1 — TDD helper + lint ✅
- [x] Добавить `_context_stats` в `LLMClient` модуль
- [x] Написать 3 unit теста

### Phase 2 — Config + .env.example ✅

### Phase 3 — Рефактор `LLMClient.chat()` лога ✅

### Phase 4 — Full test run + lint ✅ — 27/27 green, ruff clean

### Phase 5 — Docs update ✅ — architecture § 5, context-dump Flow 2 step 10, tech-stack env table

### Phase 6 — Manual smoke ✅ partial — user диалог verified, env gate verified; summarization path pending реальный 6+ диалог

### Phase 7 — Merge ✅ — master commit `7adcef1` (feat) + `605d59d` (docs)

---

## Regression watch

- Existing `test_chat_success`, `test_chat_timeout`, `test_chat_connection_error` — все мокают `_client.post` (HTTP), логирование происходит до HTTP вызова. Не должны сломаться.
- `Summarizer._call_llm` использует `LLMClient.chat()` — расширенный лог покрывает и summarization. Проверено архитектурно.

---

## Links

- [change-request.md](../change-request.md) § D-08
- [architecture.md](../architecture.md) — будет дополнен bullet про observability
- [context-dump.md Flow 2](../context-dump.md) — step 9 расширит описание лога

---

## History

- 2026-04-15 — task started, вариант A утверждён (LLMClient-level logging with env gate), spec записан
- 2026-04-15 — implementation (commit `7adcef1`), docs (commit `605d59d`), merge в master
- 2026-04-16 — prod rebuild (`make build && make restart`), зафиксирован live `llm_request` event для user диалога @StasMura: `total_chars=76, estimated_tokens=19, messages_count=2` + полный payload
- 2026-04-16 — verified env gate: `LOG_CONTEXT_FULL=false` → messages field отсутствует в event (subprocess smoke в контейнере)
