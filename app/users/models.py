from dataclasses import dataclass


@dataclass
class User:
    telegram_id: int
    current_model: str | None
    created_at: str
