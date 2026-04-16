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
        return history  # stub — filled in Task 3
