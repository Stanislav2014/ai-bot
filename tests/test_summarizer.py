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
