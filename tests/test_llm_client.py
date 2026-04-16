from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from app.llm.client import LLMClient, LLMError, _context_stats


def test_context_stats_counts_chars_and_tokens() -> None:
    messages = [
        {"role": "system", "content": "Hi"},
        {"role": "user", "content": "Hello world"},
    ]
    total_chars, est_tokens = _context_stats(messages)
    assert total_chars == 13
    assert est_tokens == 3


def test_context_stats_empty_messages() -> None:
    assert _context_stats([]) == (0, 0)


def test_context_stats_ignores_missing_content_field() -> None:
    assert _context_stats([{"role": "system"}]) == (0, 0)


@pytest_asyncio.fixture
async def llm():
    client = LLMClient()
    yield client
    await client.close()


async def test_chat_success(llm):
    mock_response = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"total_tokens": 15},
        },
        request=httpx.Request("POST", "http://test"),
    )

    with patch.object(llm._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await llm.chat([{"role": "user", "content": "Hi"}], model="test")
        assert result["content"] == "Hello!"
        assert result["tokens_used"] == 15


async def test_chat_timeout(llm):
    with patch.object(
        llm._client,
        "post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        with pytest.raises(LLMError, match="timed out"):
            await llm.chat([{"role": "user", "content": "Hi"}])


async def test_chat_connection_error(llm):
    with patch.object(
        llm._client,
        "post",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises(LLMError, match="Cannot connect"):
            await llm.chat([{"role": "user", "content": "Hi"}])
