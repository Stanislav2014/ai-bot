from dataclasses import dataclass


@dataclass(frozen=True)
class UserCreated:
    telegram_id: int
    created_at: str


@dataclass(frozen=True)
class MessageReceived:
    telegram_id: int
    text: str


@dataclass(frozen=True)
class ResponseGenerated:
    telegram_id: int
    text: str


@dataclass(frozen=True)
class HistorySummarized:
    telegram_id: int
    messages: list[dict[str, str]]


@dataclass(frozen=True)
class HistoryResetRequested:
    telegram_id: int
