import asyncio
import signal

import structlog
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import BotHandlers
from app.bot.middleware import LoggingMiddleware
from app.config import settings
from app.llm.client import LLMClient
from app.logging_config import setup_logging


async def run() -> None:
    setup_logging()
    logger = structlog.get_logger()
    logger.info("starting_bot", model=settings.default_model, llm_url=settings.llm_base_url)

    llm = LLMClient()
    handlers = BotHandlers(llm=llm)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Logging middleware — logs all incoming messages
    app.add_handler(LoggingMiddleware(), group=-1)

    # Command handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("models", handlers.models))
    app.add_handler(CommandHandler("model", handlers.set_model))

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
