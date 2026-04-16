from unittest.mock import AsyncMock

import pytest

from app.history import Summarizer


@pytest.fixture
def llm_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value={"content": "Summary text", "tokens_used": 10})
    return mock


async def test_maybe_summarize_below_threshold_returns_same_list(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=5, keep_recent=2, model="test-model")
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = await summarizer.maybe_summarize(history)
    assert result is history
    llm_mock.chat.assert_not_called()


async def test_disabled_threshold_zero_always_returns_same(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=0, keep_recent=2, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(100)]
    result = await summarizer.maybe_summarize(history)
    assert result is history
    llm_mock.chat.assert_not_called()


async def test_over_threshold_returns_summary_plus_recent(
    llm_mock: AsyncMock,
) -> None:
    summarizer = Summarizer(llm_mock, threshold=5, keep_recent=2, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(6)]
    result = await summarizer.maybe_summarize(history)
    assert len(result) == 3
    assert result[0] == {
        "role": "system",
        "content": "Previous conversation summary: Summary text",
    }
    assert result[1] == {"role": "user", "content": "m4"}
    assert result[2] == {"role": "user", "content": "m5"}
    llm_mock.chat.assert_called_once()


async def test_summary_message_role_is_system(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result[0]["role"] == "system"
    assert result[0]["content"].startswith("Previous conversation summary: ")


async def test_keep_recent_preserved_intact(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=2, model="test-model")
    history = [
        {"role": "user", "content": "m0"},
        {"role": "assistant", "content": "m1"},
        {"role": "user", "content": "m2"},
        {"role": "assistant", "content": "m3"},
        {"role": "user", "content": "m4"},
    ]
    result = await summarizer.maybe_summarize(history)
    assert result[-2] == {"role": "assistant", "content": "m3"}
    assert result[-1] == {"role": "user", "content": "m4"}


async def test_llm_call_payload_contains_transcript(llm_mock: AsyncMock) -> None:
    summarizer = Summarizer(llm_mock, threshold=2, keep_recent=1, model="test-model")
    history = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуй"},
        {"role": "user", "content": "Как дела?"},
    ]
    await summarizer.maybe_summarize(history)
    call_args = llm_mock.chat.call_args
    payload = call_args.args[0]
    assert payload[0]["role"] == "system"
    user_content = payload[1]["content"]
    assert "user: Привет" in user_content
    assert "assistant: Здравствуй" in user_content
    assert call_args.kwargs["model"] == "test-model"


async def test_summary_llm_failure_returns_original(llm_mock: AsyncMock) -> None:
    llm_mock.chat = AsyncMock(side_effect=RuntimeError("boom"))
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result is history


async def test_summary_empty_response_returns_original(llm_mock: AsyncMock) -> None:
    llm_mock.chat = AsyncMock(return_value={"content": "   \n  "})
    summarizer = Summarizer(llm_mock, threshold=3, keep_recent=1, model="test-model")
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    result = await summarizer.maybe_summarize(history)
    assert result is history
