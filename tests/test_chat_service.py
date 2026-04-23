from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.chat import ChatService, Summarizer
from app.history import HistoryStore
from app.users import UserService, UserStore


@pytest.fixture
def history(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "history", max_messages=20)


@pytest.fixture
def users(tmp_path: Path) -> UserService:
    return UserService(UserStore(tmp_path / "users"), default_model="default-model")


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
    system_prompt: str = "SYSTEM",
) -> ChatService:
    return ChatService(
        users=users,
        history=history,
        summarizer=summarizer,
        llm=llm,
        system_prompt=system_prompt,
    )


async def test_reply_returns_llm_content(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    reply = await chat.reply(1, "hi")
    assert reply == "hello reply"


async def test_reply_uses_user_selected_model(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    await users.set_model(1, "qwen3:0.6b")
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)

    await chat.reply(1, "hi")
    llm.chat.assert_awaited_once()
    _, kwargs = llm.chat.call_args
    assert kwargs["model"] == "qwen3:0.6b"


async def test_reply_uses_default_model_when_user_has_none(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    await chat.reply(1, "hi")
    _, kwargs = llm.chat.call_args
    assert kwargs["model"] == "default-model"


async def test_reply_builds_messages_with_system_prompt_and_history(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    await history.append(1, "user", "old user msg")
    await history.append(1, "assistant", "old assistant msg")

    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm, system_prompt="SP")
    await chat.reply(1, "new question")

    sent = llm.chat.call_args.args[0]
    assert sent == [
        {"role": "system", "content": "SP"},
        {"role": "user", "content": "old user msg"},
        {"role": "assistant", "content": "old assistant msg"},
        {"role": "user", "content": "new question"},
    ]


async def test_reply_appends_user_and_assistant_to_history(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    await chat.reply(1, "hi")

    saved = await history.get(1)
    assert saved == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello reply"},
    ]


async def test_reply_does_not_append_history_if_llm_fails(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    from app.llm.client import LLMError

    llm.chat = AsyncMock(side_effect=LLMError("boom"))
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)

    with pytest.raises(LLMError):
        await chat.reply(1, "hi")

    assert await history.get(1) == []


async def test_reply_invokes_summarization(
    users: UserService, history: HistoryStore, llm: AsyncMock
) -> None:
    # threshold=2, keep_recent=1 → after 3 messages summarize
    summarizer = Summarizer(llm=llm, threshold=2, keep_recent=1, model="default-model")
    for i in range(3):
        await history.append(1, "user", f"m{i}")
    # llm.chat is used for both summarize and reply — each call returns "hello reply"
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    await chat.reply(1, "new")

    # After summarize: history was replaced; first message should be a system summary
    saved = await history.get(1)
    assert saved[0]["role"] == "system"
    assert "Previous conversation summary" in saved[0]["content"]


async def test_list_models_proxies_to_llm(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    assert await chat.list_models() == ["m1", "m2"]
    llm.list_models.assert_awaited_once()


async def test_reset_history_clears_user_history(
    users: UserService, history: HistoryStore, summarizer: Summarizer, llm: AsyncMock
) -> None:
    await history.append(1, "user", "stuff")
    chat = make_chat(users=users, history=history, summarizer=summarizer, llm=llm)
    await chat.reset_history(1)

    assert await history.get(1) == []
