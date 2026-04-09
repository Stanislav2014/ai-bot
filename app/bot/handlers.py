import structlog
from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.db.repository import Database
from app.llm.client import AVAILABLE_MODELS, LLMClient, LLMError

logger = structlog.get_logger()


class BotHandlers:
    def __init__(self, db: Database, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm
        self.user_models: dict[int, str] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info("command_start", user_id=user.id, username=user.username)
        await update.message.reply_text(
            f"Hello, {user.first_name}! I'm a local LLM bot.\n\n"
            f"Current model: {self._get_model(user.id)}\n\n"
            "Commands:\n"
            "/models — list available models\n"
            "/model <name> — switch model\n"
            "/stats — your prompt statistics\n"
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
        lines = []
        for m in sorted(installed):
            marker = " (current)" if m == current else ""
            lines.append(f"• {m}{marker}")
        if not lines:
            await update.message.reply_text("No models installed. Ask admin to run: make pull-models")
            return
        await update.message.reply_text(
            "Installed models:\n" + "\n".join(lines) + "\n\nUse /model <name> to switch."
        )

    async def set_model(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Usage: /model <name>\nExample: /model qwen3:0.6b")
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

    async def stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        try:
            data = await self.db.get_stats(user_id=user_id)
            total_data = await self.db.get_stats()
            lines = [
                f"Your prompts: {data['total_prompts']}",
                f"Total prompts (all users): {total_data['total_prompts']}",
                "",
                "Your usage by model:",
            ]
            for model, count in data["by_model"].items():
                lines.append(f"  • {model}: {count}")
            if not data["by_model"]:
                lines.append("  (no prompts yet)")
            await update.message.reply_text("\n".join(lines))
        except Exception:
            logger.exception("stats_error", user_id=user_id)
            await update.message.reply_text("Failed to retrieve stats. Please try again.")

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
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": text},
        ]

        try:
            await update.message.chat.send_action("typing")
            result = await self.llm.chat(messages, model=model)
            reply = result["content"]
            tokens = result.get("tokens_used")

            # Log prompt and response to database
            await self.db.log_prompt(
                user_id=user_id,
                username=user.username,
                model=model,
                prompt=text,
                response=reply,
                tokens_used=tokens,
            )

            await update.message.reply_text(reply)

        except LLMError as e:
            logger.error("llm_error", user_id=user_id, error=str(e))
            try:
                await self.db.log_prompt(
                    user_id=user_id,
                    username=user.username,
                    model=model,
                    prompt=text,
                    response=f"[ERROR] {e}",
                    tokens_used=None,
                )
            except Exception:
                logger.exception("failed_to_log_error_prompt")
            error_msg = str(e)
            if "404" in error_msg:
                await update.message.reply_text(
                    f"Model '{model}' is not available. Use /models to see installed models."
                )
            else:
                await update.message.reply_text(
                    "Sorry, the language model is currently unavailable. Please try again later."
                )
        except Exception:
            logger.exception("unexpected_error", user_id=user_id)
            try:
                await self.db.log_prompt(
                    user_id=user_id,
                    username=user.username,
                    model=model,
                    prompt=text,
                    response="[ERROR] Unexpected error",
                    tokens_used=None,
                )
            except Exception:
                logger.exception("failed_to_log_error_prompt")
            await update.message.reply_text(
                "An unexpected error occurred. Please try again later."
            )

    def _get_model(self, user_id: int) -> str:
        return self.user_models.get(user_id, settings.default_model)
