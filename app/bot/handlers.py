import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.llm.client import LLMClient, LLMError

logger = structlog.get_logger()

SYSTEM_PROMPT = "You are a helpful assistant. Answer concisely and accurately."


class BotHandlers:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self.user_models: dict[int, str] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info("command_start", user_id=user.id, username=user.username)
        await update.message.reply_text(
            f"Hello, {user.first_name}! I'm a local LLM bot.\n\n"
            f"Current model: {self._get_model(user.id)}\n\n"
            "Commands:\n"
            "/models — choose a model\n"
            "/help — show this message"
        )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await self.start(update, context)

    async def models(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        current = self._get_model(user_id)
        installed = await self.llm.list_models()
        if not installed:
            await update.message.reply_text("No models installed. Ask admin to run: make pull-models")
            return

        buttons = []
        for m in sorted(installed):
            label = f"{'> ' if m == current else ''}{m}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"model:{m}")])

        await update.message.reply_text(
            f"Current model: {current}\nTap to switch:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def model_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        model_name = query.data.removeprefix("model:")

        self.user_models[user_id] = model_name
        logger.info("model_changed", user_id=user_id, model=model_name)

        # Update the keyboard to reflect new selection
        installed = await self.llm.list_models()
        buttons = []
        for m in sorted(installed):
            label = f"{'> ' if m == model_name else ''}{m}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"model:{m}")])

        await query.edit_message_text(
            f"Switched to: {model_name}\nTap to switch:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def set_model(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Usage: /model <name>\nOr use /models for buttons.")
            return
        model_name = context.args[0]
        installed = await self.llm.list_models()
        if installed and model_name not in installed:
            await update.message.reply_text(
                f"Model '{model_name}' is not installed.\n\n"
                f"Available: {', '.join(installed)}"
            )
            return
        self.user_models[user_id] = model_name
        logger.info("model_changed", user_id=user_id, model=model_name)
        await update.message.reply_text(f"Model switched to: {model_name}")

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        user_id = user.id
        text = update.message.text
        model = self._get_model(user_id)

        logger.info(
            "user_message",
            user_id=user_id,
            username=user.username,
            model=model,
            text_length=len(text),
        )

        # Each message is independent — no dialog history (per spec)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

        try:
            await update.message.chat.send_action("typing")
            result = await self.llm.chat(messages, model=model)
            reply = result["content"]

            logger.info("llm_reply", user_id=user_id, model=model, reply_length=len(reply))
            await update.message.reply_text(reply)

        except LLMError as e:
            logger.error("llm_error", user_id=user_id, error=str(e))
            if "404" in str(e):
                await update.message.reply_text(
                    f"Model '{model}' is not available. Use /models to see installed models."
                )
            else:
                await update.message.reply_text(
                    "Sorry, the language model is currently unavailable. Please try again later."
                )
        except Exception:
            logger.exception("unexpected_error", user_id=user_id)
            await update.message.reply_text(
                "An unexpected error occurred. Please try again later."
            )

    def _get_model(self, user_id: int) -> str:
        return self.user_models.get(user_id, settings.default_model)
