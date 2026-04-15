# Workflow ведения задач

Процесс строится вокруг TDD + manbot-style kanban + karpathy-guidelines.

## 1. Task prefixes

Все задачи в [tasks.md](tasks.md) и файлы в `docs/tasks/` используют префиксы:

| Префикс | Фаза | Когда |
|---------|------|-------|
| **A-** | Phase A | Критичные дефекты (P0/P1) |
| **B-** | Phase B | Исправленные баги (история) |
| **C-** | Phase C | Технический долг (TD) |
| **D-** | Phase D | Фичи / enhancements |

Формат файла: `{PREFIX}-{NN}_{TICKET}_{SHORT_SLUG}.md`

Пример: `D-01_BOT-12_INLINE_MODEL_SWITCH.md`

Нумерация сквозная внутри фазы, гапы разрешены.

## 2. Branch naming

| Префикс | Когда |
|---------|-------|
| `bugfix/{ticket}` | Дефекты |
| `feature/BAU/{ticket}` | Фичи < 20 раб. дней (Business As Usual) |
| `feature/CR/{ticket}` | Фичи > 20 раб. дней (Change Request) |
| `feature/TD/{ticket}` | Технический долг |

## 3. Жизненный цикл задачи

1. **Создание**
   - Скопировать структуру из [change-request-doc.md](change-request-doc.md) в [change-request.md](change-request.md), заполнить реальными данными
   - Добавить строку в [tasks.md](tasks.md) в нужную фазу
   - Перенести в [current-sprint.md](current-sprint.md) → `To Do`
   - Создать спеку в `docs/tasks/{PREFIX}-{NN}_*.md` — **единая точка истины** для задачи (design + план + история). `change-request.md` дублирует live-tracking, task spec — каноническое описание.
   - ⚠ **Не использовать `docs/superpowers/specs/`** для новых задач — эта папка архив для оригинального MVP-дизайна.

2. **Research**
   - Grep кодбейза, git log, смежные задачи, внешние зависимости
   - Собрать список Uncertainty (что неясно) + Action items (что точно делать)

3. **Implementation (TDD phases)**
   - Phase 0: Research
   - Phase 1: Core changes (backend/handler/client)
   - Phase 2: UI (если применимо)
   - Phase 3: Gating / error handling
   - Phase 4: Testing
   - Phase 5: Review & docs
   - В конце каждой фазы — checkpoint

4. **TDD-цикл на каждое изменение**
   - **RED** — падающий тест
   - **GREEN** — минимальный код чтобы тест прошёл
   - **REFACTOR** — SOLID/DRY/KISS, scope не расширять
   - НЕ батчить тесты в конец задачи

5. **Commit & merge**
   - Каждый коммит — osмысленный, одна логическая единица
   - Описательные сообщения
   - Merge в master только после зелёных тестов + линта

6. **Post-merge**
   - Обновить changelog/history в task spec
   - Пометить в [tasks.md](tasks.md) ✅
   - Перенести в `Done` в [current-sprint.md](current-sprint.md)
   - Очистить [change-request.md](change-request.md) (вернуть в template state)
   - Обновить [legacy-warning.md](legacy-warning.md), если задача добавила/убрала тех-долг

## 4. TDD — mandatory

Каждая строка production-кода должна быть покрыта тестом, написанным **до** неё.

Исключения:
- Скрипты деплоя / Makefile / CI
- Trivial DTO без логики

## 5. Karpathy guidelines

Активная skill: [.claude/skills/karpathy-guidelines/](../.claude/skills/karpathy-guidelines/SKILL.md)

1. **Think before coding** — surface assumptions, ask if unclear
2. **Simplicity first** — нулевое количество speculative features
3. **Surgical changes** — менять только то что нужно для задачи
4. **Goal-driven execution** — verifiable success criteria

## 6. Комментарии в коде

- **Дефолт — не писать комментариев**. Имена переменных объясняют WHAT.
- Только если WHY non-obvious: hidden constraint, workaround, subtle invariant.
- **НЕ писать** в коде: ticket-id, «used by X», даты, описания задач — это живёт в git log / task spec и гниёт в коде.

## 7. Action items tracking

Если задача имеет pending sub-items — создавать **concrete action items** (не uncertainty!) в спеке с:
- Уникальным ID (A1, A2, ...)
- Описанием текущего состояния
- Вариантами реализации
- Verify-критериями
- Владельцем / зависимостями

Дубликат в `change-request.md § Pending action items` как checkbox-лист.

## 8. Верификация до claim completion

Перед тем как сказать «готово»:
- Запустить тесты: `make test`
- Запустить линт: `make lint`
- Если UI изменение — проверить в Telegram вручную
- Зафиксировать результат в task spec checkpoint

## 9. Память между сессиями

Файлы в `~/.claude/projects/<project>/memory/MEMORY.md` (индекс) + `<category>_<name>.md` (детали).
После значимой задачи — добавить запись про её итог + root cause + решение.
