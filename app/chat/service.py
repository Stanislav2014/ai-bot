import structlog

from app.chat.summarizer import Summarizer
from app.history import HistoryStore
from app.llm.client import LLMClient
from app.users import UserService

logger = structlog.get_logger()


class ChatService:
    def __init__(
        self,
        users: UserService,
        history: HistoryStore,
        summarizer: Summarizer,
        llm: LLMClient,
        system_prompt: str,
    ) -> None:
        self._users = users
        self._history = history
        self._summarizer = summarizer
        self._llm = llm
        self._system_prompt = system_prompt

    async def reply(self, telegram_id: int, text: str) -> str:
        model = await self._users.get_model(telegram_id)

        history_msgs = await self._history.get(telegram_id)
        new_history = await self._summarizer.maybe_summarize(history_msgs)
        if new_history is not history_msgs:
            await self._history.replace(telegram_id, new_history)
            logger.info(
                "history_summarized",
                user_id=telegram_id,
                before=len(history_msgs),
                after=len(new_history),
            )
            history_msgs = new_history

        messages = (
            [{"role": "system", "content": self._system_prompt}]
            + history_msgs
            + [{"role": "user", "content": text}]
        )

        result = await self._llm.chat(messages, model=model)
        reply = result["content"]

        await self._history.append(telegram_id, "user", text)
        await self._history.append(telegram_id, "assistant", reply)

        logger.info(
            "llm_reply",
            user_id=telegram_id,
            model=model,
            reply_length=len(reply),
            history_len=len(history_msgs) + 2,
        )
        return reply

    async def list_models(self) -> list[str]:
        return await self._llm.list_models()

    async def reset_history(self, telegram_id: int) -> None:
        await self._history.reset(telegram_id)
