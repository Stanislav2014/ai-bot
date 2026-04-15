# Documentation Index — ai-bot

Структура вдохновлена [manbot](https://github.com/larchanka/manbot) + TDD-методология + karpathy guidelines.

## Стратегия / процесс / доска

| Файл | Назначение |
|------|-----------|
| [project.md](project.md) | Обзор проекта на 1 экран |
| [instructions.md](instructions.md) | Workflow ведения задач (TDD, branch naming, commit/merge) |
| [plan.md](plan.md) | Roadmap по фазам |
| [ideas.md](ideas.md) | Копилка идей (ещё не задачи) |
| [discuss.md](discuss.md) | Открытые архитектурные / продуктовые вопросы |
| [tasks.md](tasks.md) | Master-каталог задач по фазам (A-/B-/C-/D-) |
| [current-sprint.md](current-sprint.md) | Kanban текущей итерации |
| [change-request.md](change-request.md) | Реальные данные текущей задачи |
| [change-request-doc.md](change-request-doc.md) | Шаблон change-request |
| [tasks/](tasks/) | Детальные спеки задач |

## Архитектура / технический атлас

| Файл | Назначение |
|------|-----------|
| [architecture.md](architecture.md) | Архитектурные паттерны + **Edge cases** |
| [context-dump.md](context-dump.md) | Карта всех потоков взаимодействия (с file:line) |
| [tech-stack.md](tech-stack.md) | Backend / infra стек, версии |
| [db-schema.md](db-schema.md) | Состояние хранения данных (сейчас stateless) |
| [ui-kit.md](ui-kit.md) | Telegram UI: команды, сообщения, inline-клавиатура |
| [testing.md](testing.md) | Тестовые фреймворки, fixtures, команды |
| [legacy-warning.md](legacy-warning.md) | Каталог тех-долга / костылей / known issues |
| [links.md](links.md) | Внешние ссылки, официальные доки стека |

## Контракты

| Файл | Назначение |
|------|-----------|
| [contracts/README.md](contracts/README.md) | Индекс всех внешних интерфейсов |
| [contracts/external/telegram.md](contracts/external/telegram.md) | Telegram Bot API |
| [contracts/external/ollama.md](contracts/external/ollama.md) | Ollama / Lemonade OpenAI-compatible API |

## История создания (архив)

| Файл | Назначение |
|------|-----------|
| [prompts.md](prompts.md) | История промптов к Claude Code при создании проекта |
| [time-log.md](time-log.md) | Лог затраченного времени |
| [superpowers/specs/](superpowers/specs/) | **Архив** — только оригинальная MVP-спека (2026-04-09). Новые задачи сюда не пишутся. |

> **Конвенция**: все task-specs (включая дизайн) живут в [tasks/](tasks/). Одна задача — один файл. `superpowers/specs/` не расширяется новыми задачами.

## Конвенции

- **Task prefixes**: A- (критичные дефекты), B- (исправленные баги), C- (тех-долг), D- (фичи)
- **Branch naming**: `bugfix/XXXX`, `feature/BAU/XXXX`, `feature/CR/XXXX`, `feature/TD/XXXX`
- **TDD mandatory**: RED → GREEN → REFACTOR, тест до кода
- **Karpathy guidelines**: simplicity first, surgical changes, goal-driven
- **Комментарии в коде**: по дефолту не писать; только если WHY non-obvious
