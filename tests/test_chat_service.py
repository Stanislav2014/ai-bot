from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.chat import ChatService, Summarizer
from app.events import (
    EventBus,
    HistoryResetRequested,
    HistorySummarized,
    MessageReceived,
    ResponseGenerated,
)
from app.history import HistoryStore
from app.users import UserService, UserStore


@pytest.fixture
def history(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "history", max_messages=20)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def users(tmp_path: Path, bus: EventBus) -> UserService:
    return UserService(
        UserStore(tmp_path / "users"),
        default_model="default-model",
        bus=bus,
    )


@pytest.fixture
def llm() -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value={"content": "hello reply", "tokens_used": 42})
    mock.list_models = AsyncMock(return_value=["m1", "m2"])
    return mock


@pytest.fixture
def summarizer(llm: AsyncMock) -> Summarizer:
    return Summarizer(llm=llm, threshold=0, keep_recent=2, model="default-model")


def make_chat(
    *,
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
    system_prompt: str = "SYSTEM",
) -> ChatService:
    return ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt=system_prompt,
    )


class _EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[object] = []
        bus.subscribe(MessageReceived, self._record)
        bus.subscribe(ResponseGenerated, self._record)
        bus.subscribe(HistorySummarized, self._record)

    async def _record(self, event: object) -> None:
        self.events.append(event)


async def test_reply_returns_llm_content(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    reply = await chat.reply(1, "hi")
    assert reply == "hello reply"


async def test_reply_uses_user_selected_model(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    await users.set_model(1, "qwen3:0.6b")
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)

    await chat.reply(1, "hi")
    llm.chat.assert_awaited_once()
    _, kwargs = llm.chat.call_args
    assert kwargs["model"] == "qwen3:0.6b"


async def test_reply_uses_default_model_when_user_has_none(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    await chat.reply(1, "hi")
    _, kwargs = llm.chat.call_args
    assert kwargs["model"] == "default-model"


async def test_reply_builds_messages_with_system_prompt_and_history(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    await history.append(1, "user", "old user msg")
    await history.append(1, "assistant", "old assistant msg")

    chat = make_chat(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt="SP",
    )
    await chat.reply(1, "new question")

    sent = llm.chat.call_args.args[0]
    assert sent == [
        {"role": "system", "content": "SP"},
        {"role": "user", "content": "old user msg"},
        {"role": "assistant", "content": "old assistant msg"},
        {"role": "user", "content": "new question"},
    ]


async def test_reply_publishes_message_then_response(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    collector = _EventCollector(bus)
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)

    await chat.reply(1, "hi")

    assert collector.events == [
        MessageReceived(telegram_id=1, text="hi"),
        ResponseGenerated(telegram_id=1, text="hello reply"),
    ]


async def test_reply_does_not_call_history_writes(
    users: UserService,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
    tmp_path: Path,
) -> None:
    """ChatService must not write to history directly — writes go through events."""
    history = HistoryStore(tmp_path / "history", max_messages=20)
    history.append = AsyncMock(side_effect=AssertionError("history.append must not be called"))
    history.replace = AsyncMock(side_effect=AssertionError("history.replace must not be called"))
    history.reset = AsyncMock(side_effect=AssertionError("history.reset must not be called"))

    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    await chat.reply(1, "hi")

    history.append.assert_not_called()
    history.replace.assert_not_called()
    history.reset.assert_not_called()


async def test_reply_does_not_publish_if_llm_fails(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    from app.llm.client import LLMError

    llm.chat = AsyncMock(side_effect=LLMError("boom"))
    collector = _EventCollector(bus)
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)

    with pytest.raises(LLMError):
        await chat.reply(1, "hi")

    # Both events must be skipped — caller can retry without duplicates.
    assert collector.events == []


async def test_reply_publishes_history_summarized_before_message(
    users: UserService,
    history: HistoryStore,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    # threshold=2, keep_recent=1 → after 3 messages summarize
    summarizer = Summarizer(llm=llm, threshold=2, keep_recent=1, model="default-model")
    for i in range(3):
        await history.append(1, "user", f"m{i}")

    collector = _EventCollector(bus)
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    await chat.reply(1, "new")

    types = [type(e).__name__ for e in collector.events]
    assert types == ["HistorySummarized", "MessageReceived", "ResponseGenerated"]
    assert isinstance(collector.events[0], HistorySummarized)
    assert collector.events[0].telegram_id == 1
    assert collector.events[0].messages[0]["role"] == "system"
    assert "Previous conversation summary" in collector.events[0].messages[0]["content"]


async def test_list_models_proxies_to_llm(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    assert await chat.list_models() == ["m1", "m2"]
    llm.list_models.assert_awaited_once()


async def test_reset_history_publishes_history_reset_requested(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    received: list[HistoryResetRequested] = []

    async def handler(event: HistoryResetRequested) -> None:
        received.append(event)

    bus.subscribe(HistoryResetRequested, handler)
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    await chat.reset_history(1)

    assert received == [HistoryResetRequested(telegram_id=1)]


async def test_reset_history_does_not_call_history_reset(
    users: UserService,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
    tmp_path: Path,
) -> None:
    history = HistoryStore(tmp_path / "history", max_messages=20)
    history.reset = AsyncMock(side_effect=AssertionError("history.reset must not be called"))

    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, bus=bus)
    await chat.reset_history(1)

    history.reset.assert_not_called()


async def test_reply_returns_canned_message_when_llm_disabled(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    chat = ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt="SP",
        llm_enabled=False,
        llm_disabled_reply="AI is off",
    )

    reply = await chat.reply(1, "hi")
    assert reply == "AI is off"


async def test_reply_does_not_call_llm_when_disabled(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    chat = ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt="SP",
        llm_enabled=False,
    )

    await chat.reply(1, "hi")
    llm.chat.assert_not_called()


async def test_reply_does_not_publish_events_when_llm_disabled(
    users: UserService,
    history: HistoryStore,
    summarizer: Summarizer,
    llm: AsyncMock,
    bus: EventBus,
) -> None:
    collector = _EventCollector(bus)
    chat = ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        bus=bus,
        system_prompt="SP",
        llm_enabled=False,
    )

    await chat.reply(1, "hi")
    assert collector.events == []
