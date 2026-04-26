from typing import Protocol

import structlog

from app.chat.summarizer import Summarizer
from app.events import (
    EventBus,
    HistoryResetRequested,
    HistorySummarized,
    MessageReceived,
    ResponseGenerated,
)
from app.llm.client import LLMClient
from app.users import UserService

logger = structlog.get_logger()


class HistoryReader(Protocol):
    async def get(self, telegram_id: int) -> list[dict[str, str]]: ...


class ChatService:
    def __init__(
        self,
        users: UserService,
        history: HistoryReader,
        summarizer: Summarizer,
        llm: LLMClient,
        bus: EventBus,
        system_prompt: str,
    ) -> None:
        self._users = users
        self._history = history
        self._summarizer = summarizer
        self._llm = llm
        self._bus = bus
        self._system_prompt = system_prompt

    async def reply(self, telegram_id: int, text: str) -> str:
        model = await self._users.get_model(telegram_id)

        history_msgs = await self._history.get(telegram_id)
        new_history = await self._summarizer.maybe_summarize(history_msgs)
        if new_history is not history_msgs:
            await self._bus.publish(
                HistorySummarized(telegram_id=telegram_id, messages=new_history)
            )
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

        await self._bus.publish(MessageReceived(telegram_id=telegram_id, text=text))
        await self._bus.publish(ResponseGenerated(telegram_id=telegram_id, text=reply))

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
        await self._bus.publish(HistoryResetRequested(telegram_id=telegram_id))
