import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

AVAILABLE_MODELS = [
    "gpt-oss-20b",
    "qwen3:0.6b",
    "qwen3.5:27b",
]


def _context_stats(messages: list[dict[str, str]]) -> tuple[int, int]:
    """Return (total_chars, estimated_tokens). Tokens = chars // 4 heuristic."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars, total_chars // 4


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.timeout = settings.llm_timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self, messages: list[dict[str, str]], model: str | None = None
    ) -> dict:
        model = model or settings.default_model
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        total_chars, est_tokens = _context_stats(messages)
        log_data: dict = {
            "model": model,
            "messages_count": len(messages),
            "total_chars": total_chars,
            "estimated_tokens": est_tokens,
        }
        if settings.log_context_full:
            log_data["messages"] = messages
        logger.info("llm_request", **log_data)

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens")
            logger.info("llm_response", model=model, tokens=tokens)
            return {"content": content, "tokens_used": tokens}

        except httpx.TimeoutException:
            logger.error("llm_timeout", model=model, timeout=self.timeout)
            raise LLMError(f"LLM request timed out after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            logger.error("llm_http_error", model=model, status=e.response.status_code)
            raise LLMError(f"LLM returned HTTP {e.response.status_code}")
        except (KeyError, IndexError) as e:
            logger.error("llm_parse_error", model=model, error=str(e))
            raise LLMError("Failed to parse LLM response")
        except httpx.ConnectError:
            logger.error("llm_connection_error", model=model, url=self.base_url)
            raise LLMError("Cannot connect to LLM server. Is Ollama running?")

    async def list_models(self) -> list[str]:
        """Fetch installed models via OpenAI-compatible /v1/models endpoint."""
        url = f"{self.base_url}/v1/models"
        try:
            resp = await self._client.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            logger.warning("failed_to_list_models", url=url)
            return AVAILABLE_MODELS


class LLMError(Exception):
    pass
