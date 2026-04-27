import asyncio
import signal
from pathlib import Path

import structlog
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import BotHandlers
from app.bot.middleware import LoggingMiddleware
from app.chat import ChatService, Summarizer
from app.config import settings
from app.events import EventBus
from app.history import HistoryStore
from app.history.subscriber import subscribe as subscribe_history
from app.llm.client import LLMClient
from app.logging_config import setup_logging
from app.users import UserService, UserStore


async def run() -> None:
    setup_logging()
    logger = structlog.get_logger()
    summarize_model = settings.history_summarize_model or settings.default_model
    logger.info(
        "starting_bot",
        model=settings.default_model,
        llm_url=settings.llm_base_url,
        history_enabled=settings.history_enabled,
        history_dir=settings.history_dir,
        users_dir=settings.users_dir,
        history_max_messages=settings.history_max_messages,
        history_max_chars=settings.history_max_chars,
        summarize_threshold=settings.history_summarize_threshold,
        keep_recent=settings.history_keep_recent,
        summarize_model=summarize_model,
        system_prompt=settings.system_prompt[:80],
    )

    bus = EventBus()
    llm = LLMClient()
    history = HistoryStore(
        data_dir=Path(settings.history_dir),
        max_messages=settings.history_max_messages,
        max_chars=settings.history_max_chars,
        enabled=settings.history_enabled,
    )
    subscribe_history(bus, history)
    summarizer = Summarizer(
        llm=llm,
        threshold=settings.history_summarize_threshold,
        keep_recent=settings.history_keep_recent,
        model=summarize_model,
    )
    user_store = UserStore(data_dir=Path(settings.users_dir))
    users = UserService(store=user_store, default_model=settings.default_model, bus=bus)
    chat = ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt=settings.system_prompt,
        llm_enabled=settings.llm_enabled,
        llm_disabled_reply=settings.llm_disabled_reply,
    )
    handlers = BotHandlers(users=users, chat=chat)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Logging middleware — logs all incoming messages
    app.add_handler(LoggingMiddleware(), group=-1)

    # Command handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("models", handlers.models))
    app.add_handler(CommandHandler("model", handlers.set_model))
    app.add_handler(CommandHandler("reset", handlers.reset))

    # Callback handler for inline keyboard (model selection)
    app.add_handler(CallbackQueryHandler(handlers.model_callback, pattern=r"^model:"))

    # Message handler (all text messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("bot_started")

    try:
        async with app:
            await app.start()
            await app.updater.start_polling()
            await stop_event.wait()
            logger.info("shutting_down")
            await app.updater.stop()
            await app.stop()
    finally:
        await llm.close()
        logger.info("bot_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
