import asyncio
import json

import httpx
import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.chat import ChatService, LLMError
from app.config import settings
from app.users import UserService

logger = structlog.get_logger()


_SENTRY_TEST_KINDS = ("raise", "async", "external", "data")


def _is_sentry_test_allowed(user_id: int) -> bool:
    return user_id in settings.sentry_test_user_ids


async def _async_raiser() -> None:
    await asyncio.sleep(0)
    raise RuntimeError("async sentry test error from create_task")


async def _trigger_error(kind: str) -> None:
    if kind == "raise":
        raise RuntimeError("manual sentry test error")
    if kind == "data":
        json.loads("{not_valid_json")
        return
    if kind == "async":
        task = asyncio.create_task(_async_raiser())
        await task
        return
    if kind == "external":
        async with httpx.AsyncClient() as client:
            await client.get("http://127.0.0.1:1/", timeout=2.0)
        return
    raise ValueError(f"unknown sentry_test kind: {kind!r}")


class BotHandlers:
    def __init__(self, users: UserService, chat: ChatService) -> None:
        self.users = users
        self.chat = chat

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info("command_start", user_id=user.id, username=user.username)
        current = await self.users.get_model(user.id)
        await update.message.reply_text(
            f"Hello, {user.first_name}! I'm a local LLM bot.\n\n"
            f"Current model: {current}\n\n"
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
        current = await self.users.get_model(user_id)
        installed = await self.chat.list_models()
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
        previous = await self.users.get_model(user_id)

        await self.users.set_model(user_id, model_name)
        logger.info(
            "model_changed",
            user_id=user_id,
            username=username,
            previous_model=previous,
            new_model=model_name,
        )

        # Update the keyboard to reflect new selection
        installed = await self.chat.list_models()
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
        installed = await self.chat.list_models()
        if installed and model_name not in installed:
            await update.message.reply_text(
                f"Model '{model_name}' is not installed.\n\n"
                f"Available: {', '.join(installed)}"
            )
            return
        previous = await self.users.get_model(user_id)
        await self.users.set_model(user_id, model_name)
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
        model = await self.users.get_model(user_id)

        logger.info(
            "user_message",
            user_id=user_id,
            username=user.username,
            model=model,
            text_length=len(text),
        )

        try:
            await update.message.chat.send_action("typing")
            reply = await self.chat.reply(user_id, text)
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
        await self.chat.reset_history(user.id)
        logger.info("history_reset", user_id=user.id, username=user.username)
        await update.message.reply_text("История диалога очищена.")

    async def sentry_test(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        if not _is_sentry_test_allowed(user_id):
            await update.message.reply_text("Команда недоступна.")
            return

        kind = (context.args[0] if context.args else "").lower()
        if kind not in _SENTRY_TEST_KINDS:
            await update.message.reply_text(
                f"Usage: /sentry_test <{'|'.join(_SENTRY_TEST_KINDS)}>"
            )
            return

        logger.info("sentry_test_triggered", user_id=user_id, kind=kind)
        await _trigger_error(kind)
