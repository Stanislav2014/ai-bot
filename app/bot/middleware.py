import structlog
from telegram import Update
from telegram.ext import BaseHandler

logger = structlog.get_logger()


class LoggingMiddleware(BaseHandler):
    """Logs every incoming update for observability."""

    def __init__(self) -> None:
        super().__init__(callback=self._noop)

    @staticmethod
    async def _noop(update: Update, context) -> None:
        pass

    def check_update(self, update: object) -> bool:
        if isinstance(update, Update) and update.message:
            msg = update.message
            logger.info(
                "incoming_message",
                user_id=msg.from_user.id if msg.from_user else None,
                username=msg.from_user.username if msg.from_user else None,
                chat_id=msg.chat_id,
                text=msg.text[:200] if msg.text else None,
                message_id=msg.message_id,
            )
        return False  # Never consume the update — pass through
