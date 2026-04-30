import structlog
from telegram import Update
from telegram.ext import BaseHandler

from app.observability import bind_request_context, new_trace_id

logger = structlog.get_logger()


class LoggingMiddleware(BaseHandler):
    """Binds trace_id + user_id + update_id to contextvars and logs the inbound event."""

    def __init__(self) -> None:
        super().__init__(callback=self._noop)

    @staticmethod
    async def _noop(update: Update, context) -> None:
        pass

    def check_update(self, update: object) -> bool:
        if not isinstance(update, Update):
            return False

        from_user = None
        if update.message and update.message.from_user:
            from_user = update.message.from_user
        elif update.callback_query and update.callback_query.from_user:
            from_user = update.callback_query.from_user

        bind_request_context(
            trace_id=new_trace_id(),
            update_id=update.update_id,
            user_id=from_user.id if from_user else None,
        )

        if update.message:
            msg = update.message
            logger.info(
                "incoming_message",
                username=from_user.username if from_user else None,
                chat_id=msg.chat_id,
                text=msg.text[:200] if msg.text else None,
                message_id=msg.message_id,
            )
        elif update.callback_query:
            cb = update.callback_query
            logger.info(
                "incoming_callback",
                username=from_user.username if from_user else None,
                data=cb.data,
            )

        return False
