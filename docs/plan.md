# Roadmap — ai-bot

## Фаза 0 — MVP ✅ (завершена 2026-04-09)

- [x] Telegram bot + polling
- [x] OpenAI-compatible LLM client (Ollama)
- [x] Commands: `/start`, `/help`, `/models`, `/model`
- [x] Stateless message handling
- [x] Structured logging (structlog JSON)
- [x] Graceful error handling
- [x] Docker Compose (bot + lemonade)
- [x] Makefile + deploy.sh
- [x] pytest suite для LLM client

## Фаза 1 — UX полировка ✅ (завершена 2026-04-10)

- [x] Inline keyboard для выбора модели (`/models`)
- [x] Лог переключения модели в чат-сообщения (`previous → new`)
- [x] Отдельное сообщение после переключения через inline buttons

## Фаза 2 — Migration to Lemonade (в процессе)

- [ ] Полный переход с Ollama на Lemonade (docker-compose уже переключён, но config.py default и README упоминают Ollama)
- [ ] Проверить что `lemonade/` Dockerfile корректен и загружает нужные модели
- [ ] Обновить README.md с актуальным стеком
- [ ] Выровнять `app/config.py` default с `.env.example` (lemonade:8000/api)
- [ ] Обновить Makefile `pull-models` target (сейчас вызывает `ollama pull`)

## Фаза 3 — Quality / tests

- [ ] Тесты для BotHandlers (handle_message, model_callback)
- [ ] Тест на inline keyboard rendering (currently marker vs tapped)
- [ ] Coverage отчёт в CI (если CI появится)

## Фаза 4 — Nice to have

- [ ] Persistent per-user model selection (сейчас dict в памяти, теряется при рестарте)
- [ ] Rate limiting (защита от абуза)
- [ ] Streaming ответы (опционально)
- [ ] Опциональное сохранение истории диалога (N последних сообщений)

## Заметки

- **Нет сроков** — проект в режиме maintenance.
- Фаза 2 драйвится тем, что в git status висит untracked `lemonade/` с Dockerfile. Миграция начата, но не завершена.
- Вопросы открытые — в [discuss.md](discuss.md).
