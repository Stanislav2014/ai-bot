# Change Request — TEMPLATE (один блок задачи)

> 📋 **Это шаблон одного task-блока.** Реальные данные — в [change-request.md](change-request.md), где может быть несколько таких блоков одновременно (по числу задач в спринте).
> При старте новой задачи — **добавить** этот блок в change-request.md, не заменять весь файл. После merge — оставить блок на месте со статусом Merged, удалять только при закрытии спринта.

---

## Метадата

| Поле | Значение |
|------|----------|
| **Task ID** | `{PREFIX}-{NN}` (A-01 / B-02 / C-03 / D-04) |
| **Ticket** | `BOT-XXXX` (или пусто, если без внешнего трекера) |
| **Branch** | `{type}/{slug}` (`bugfix/BOT-XXX`, `feature/BAU/BOT-XXX`, ...) |
| **Task spec** | `docs/tasks/{PREFIX}-{NN}_...md` (ссылка, если есть) |
| **Started** | YYYY-MM-DD |
| **Status** | `To Do` / `In Progress` / `In Review` / `Done` |
| **Owner** | handle / ник |

---

## Goal

Одно предложение — что именно должно измениться и почему.

## Success criteria (verifiable)

Жёсткие проверяемые критерии — по каждому должен быть тест или ручная верификация.

- [ ] Критерий 1 → verify: {{как проверить}}
- [ ] Критерий 2 → verify: {{как проверить}}
- [ ] Критерий 3 → verify: {{как проверить}}

---

## Scope

### In scope
- Что именно меняется

### Out of scope
- Что сознательно **не** трогаем в этой задаче

---

## Impact / change surface

Что и где затрагивается — каждый файл со ссылкой file:line.

### Изменяемые файлы
| Файл | Характер изменений |
|------|--------------------|
| `app/xxx.py` | описание |

### Затронутые потоки (из [context-dump.md](context-dump.md))
- Flow N: описание, как меняется

### Затронутые контракты
- contracts/external/{system}.md — что меняется

---

## Uncertainty list

Что неясно и требует решения до или в процессе работы.

1. **Вопрос 1** — текущее понимание / варианты
2. **Вопрос 2** — ...

---

## Pending action items

Concrete TODOs, которые точно нужно сделать (не uncertainty, а чёткая работа).

- [ ] **A1**: описание · verify: {{критерий}} · owner: {{handle}}
- [ ] **A2**: описание · verify: {{критерий}} · owner: {{handle}}

---

## TDD phases

### Phase 0 — Research
- [ ] Grep кодбейза по релевантным ключевым словам
- [ ] Git log: последние изменения в затрагиваемых файлах
- [ ] Смежные задачи (если есть)

### Phase 1 — Core changes
- [ ] RED: тест на новое поведение
- [ ] GREEN: минимальный код
- [ ] REFACTOR: SOLID/DRY

### Phase 2 — UI (если применимо)

### Phase 3 — Error handling / gating

### Phase 4 — Testing
- [ ] `make test` — все тесты зелёные
- [ ] `make lint` — линт зелёный
- [ ] Ручная проверка UI в Telegram (если применимо)

### Phase 5 — Review & docs
- [ ] Обновить [tasks.md](tasks.md) — пометить ✅
- [ ] Обновить [legacy-warning.md](legacy-warning.md), если задача добавила/убрала тех-долг
- [ ] Обновить [context-dump.md](context-dump.md), если изменился flow
- [ ] Обновить [contracts/](contracts/), если контракт поменялся
- [ ] В change-request.md обновить статус блока задачи на Merged (не удалять блок)

---

## Regression watch

На что обратить особое внимание при review — где потенциально можно сломать смежную функциональность.

- Area 1 — почему риск

---

## Checkpoints

Краткие отметки в конце каждой фазы — что работает, что нет.

### Phase 0 checkpoint
_(заполняется по ходу работы)_

### Phase 1 checkpoint

### Phase 4 checkpoint

---

## History

Хронология значимых событий по задаче.

- YYYY-MM-DD — started
- YYYY-MM-DD — phase 1 complete
- YYYY-MM-DD — merged (commit abc1234)
