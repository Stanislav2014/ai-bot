import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.history import HistoryStore, Summarizer
from app.llm.client import LLMClient, LLMError

logger = structlog.get_logger()

SYSTEM_PROMPT = "You are a helpful assistant. Answer concisely and accurately."


class BotHandlers:
    def __init__(
        self,
        llm: LLMClient,
        history: HistoryStore,
        summarizer: Summarizer,
    ) -> None:
        self.llm = llm
        self.history = history
        self.summarizer = summarizer
        self.user_models: dict[int, str] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info("command_start", user_id=user.id, username=user.username)
        await update.message.reply_text(
            f"Hello, {user.first_name}! I'm a local LLM bot.\n\n"
            f"Current model: {self._get_model(user.id)}\n\n"
            "Commands:\n"
            "/models — choose a model\n"
            "/reset — clear dialog history\n"
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
        username = query.from_user.username
        model_name = query.data.removeprefix("model:")
        previous = self._get_model(user_id)

        self.user_models[user_id] = model_name
        logger.info(
            "model_changed",
            user_id=user_id,
            username=username,
            previous_model=previous,
            new_model=model_name,
        )

        # Update the keyboard to reflect new selection
        installed = await self.llm.list_models()
        buttons = []
        for m in sorted(installed):
            label = f"{'> ' if m == model_name else ''}{m}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"model:{m}")])

        await query.edit_message_text(
            "Tap to switch:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        await query.message.reply_text(f"Switched: {previous} → {model_name}")

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
        previous = self._get_model(user_id)
        self.user_models[user_id] = model_name
        logger.info(
            "model_changed",
            user_id=user_id,
            username=update.effective_user.username,
            previous_model=previous,
            new_model=model_name,
        )
        await update.message.reply_text(f"Switched: {previous} → {model_name}")

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

        history_msgs = await self.history.get(user_id)
        new_history = await self.summarizer.maybe_summarize(history_msgs)
        if new_history is not history_msgs:
            await self.history.replace(user_id, new_history)
            logger.info(
                "history_summarized",
                user_id=user_id,
                before=len(history_msgs),
                after=len(new_history),
            )
            history_msgs = new_history
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history_msgs
            + [{"role": "user", "content": text}]
        )

        try:
            await update.message.chat.send_action("typing")
            result = await self.llm.chat(messages, model=model)
            reply = result["content"]

            await self.history.append(user_id, "user", text)
            await self.history.append(user_id, "assistant", reply)

            logger.info(
                "llm_reply",
                user_id=user_id,
                model=model,
                reply_length=len(reply),
                history_len=len(history_msgs) + 2,
            )
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

    async def reset(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        await self.history.reset(user.id)
        logger.info("history_reset", user_id=user.id, username=user.username)
        await update.message.reply_text("История диалога очищена.")

    def _get_model(self, user_id: int) -> str:
        return self.user_models.get(user_id, settings.default_model)
