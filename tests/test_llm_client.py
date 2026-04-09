from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from app.llm.client import LLMClient, LLMError


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
