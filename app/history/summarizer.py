import structlog

from app.llm.client import LLMClient

logger = structlog.get_logger()

SUMMARY_PROMPT = (
    "You are a conversation summarizer. Summarize the following dialog "
    "between a user and an assistant in 1-2 sentences in Russian. "
    "Preserve key facts, decisions, and open questions. "
    "Do not add commentary or meta-text. Output only the summary."
)


class Summarizer:
    def __init__(
        self,
        llm: LLMClient,
        threshold: int,
        keep_recent: int,
        model: str,
    ) -> None:
        self._llm = llm
        self._threshold = threshold
        self._keep_recent = keep_recent
        self._model = model

    async def maybe_summarize(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        if self._threshold <= 0 or len(history) <= self._threshold:
            return history
        split = max(0, len(history) - self._keep_recent)
        to_summarize = history[:split]
        recent = history[split:]
        if not to_summarize:
            return history
        try:
            summary_text = await self._call_llm(to_summarize)
        except Exception:
            logger.exception("summarize_failed")
            return history
        summary_text = summary_text.strip()
        if not summary_text:
            logger.warning("summarize_empty_response")
            return history
        summary_msg = {
            "role": "system",
            "content": f"Previous conversation summary: {summary_text}",
        }
        return [summary_msg] + recent

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        transcript = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )
        prompt = [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": transcript},
        ]
        result = await self._llm.chat(prompt, model=self._model)
        return result["content"]
