# D-09 · Dual logging — stdout + rotating file внутри проекта

| Поле | Значение |
|------|----------|
| **Task ID** | D-09 |
| **Ticket** | BOT-D09 |
| **Branch** | `feature/BAU/BOT-D09` |
| **Status** | Code complete, awaiting merge |
| **Owner** | Stan |
| **Started** | 2026-04-17 |

---

## Summary

До D-09 лог писался только в stdout и доставался через `docker compose logs`. Физический файл был внутри докеровского `/var/lib/docker/containers/...` (owner=root, через sudo). D-09 добавляет **второй output** — ротируемый файл `data/logs/bot.log` внутри проекта (bind-mount), доступный без sudo.

## Motivation

- Делиться логами (sharing / курсовая / ревью) удобнее через файл в репо-директории
- Сохранять логи между recreate'ами контейнера (volume `./data:/app/data` уже пробрасывается)
- `docker compose logs` остаётся работать — stdout дублируется

## Design

### Dual output via stdlib logging

Старый setup использовал `structlog.PrintLoggerFactory(file=sys.stdout)` — писал напрямую в stdout. Новый использует stdlib logging как backend:

```python
structlog.configure(
    processors=[..., structlog.processors.JSONRenderer()],
    logger_factory=structlog.stdlib.LoggerFactory(),  # forward to stdlib
    ...
)

handlers = [logging.StreamHandler(sys.stdout)]
if settings.log_file:
    handlers.append(logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    ))
root = logging.getLogger()
root.handlers = handlers
```

- structlog рендерит JSON-строку → stdlib распределяет на все handlers
- stdout handler → `docker compose logs` работает как раньше
- file handler → `data/logs/bot.log` + до 5 ротированных `.log.1`..`.log.5` (по 10MB каждый)

### Config

```python
# app/config.py
log_file: str = "data/logs/bot.log"   # empty = stdout only
```

### .env.example

```
LOG_FILE=data/logs/bot.log
```

### Ротация

`RotatingFileHandler(maxBytes=10_000_000, backupCount=5)`:
- Файл превышает 10MB → переименовывается в `.log.1`, новый `.log` создаётся
- Максимум 5 исторических файлов → суммарно ~50MB на диске
- Потеря данных исключена (atomic rename)

### Создание директории

`log_path.parent.mkdir(parents=True, exist_ok=True)` — создаёт `data/logs/` при первом старте. Работает под UID из `user: "${UID:-1000}:${GID:-1000}"` (D-04 permission fix покрывает).

---

## Success criteria

- [x] `settings.log_file` env поле (default `data/logs/bot.log`)
- [x] `.env.example` описывает `LOG_FILE` + rotation policy
- [x] `app/logging_config.py` рефакторен на stdlib + structlog
- [x] Stdout handler работает (`docker compose logs bot` не сломано)
- [x] Rotating file handler создаёт `data/logs/bot.log` с JSON-логами
- [x] 27 существующих тестов зелёные
- [x] `make lint` чистый
- [x] Ручной smoke: prod rebuild 2026-04-17 — `data/logs/bot.log` появился на хосте owner=stan:stan, содержит `starting_bot` + `bot_started` events в JSON
- [ ] Merge в master
- [ ] Push

---

## Scope

### In scope
- `app/logging_config.py` — refactor
- `app/config.py` — `log_file` field
- `.env.example` — LOG_FILE documented
- Docs: architecture § 5, tech-stack env table

### Out of scope
- Per-level файлы (errors separately) — YAGNI
- Интеграция с journalctl / syslog / fluentd — требует infra
- Отдельный debug-файл с полным payload — `LOG_CONTEXT_FULL` уже есть
- Compression старых rotated files — стандартные stdlib handlers не умеют без `mutex`, не окупается

---

## Uncertainty list

1. **log size growth** — при `LOG_CONTEXT_FULL=true` и реальной нагрузке файл может заполняться быстро. Ротация 10MB × 5 = 50MB total, хватает на тысячи messages. Если станет мало — crank up `backupCount` или снизить log level.
2. **Disk wear** — SSD-дружественная ротация (rename, не shuffle bytes), но в проде (dev-станция) некритично.
3. **UID ownership** — файл создаётся контейнером под UID из `user: "${UID:-1000}:${GID:-1000}"`. На host-машине с другим UID нужен override (задокументировано в .env.example ещё от D-04 fix).

---

## Regression watch

- `tests/` не тестирует setup_logging напрямую — не должны сломаться, и не сломались
- `structlog.get_logger()` используется во всём коде (handlers.py, history/*.py, llm/client.py) — API не поменялся
- JSON-формат на stdout идентичен предыдущему (те же processors, тот же renderer), backward-compat для всех downstream log parsers

---

## History

- 2026-04-17 — task started (после того как user pointed out что лог должен быть в файле внутри проекта)
- 2026-04-17 — implementation: 3 файла изменены, lint+tests зелёные
- 2026-04-17 — prod rebuild + restart, `data/logs/bot.log` подтверждён на хосте
