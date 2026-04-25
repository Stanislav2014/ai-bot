import asyncio
from dataclasses import asdict
from pathlib import Path

import structlog
import yaml

from app.users.models import User

logger = structlog.get_logger()


class UserStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._locks: dict[int, asyncio.Lock] = {}
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, telegram_id: int) -> asyncio.Lock:
        if telegram_id not in self._locks:
            self._locks[telegram_id] = asyncio.Lock()
        return self._locks[telegram_id]

    def _file(self, telegram_id: int) -> Path:
        return self._data_dir / f"{telegram_id}.yaml"

    async def load(self, telegram_id: int) -> User | None:
        async with self._lock(telegram_id):
            path = self._file(telegram_id)
            if not path.exists():
                return None
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    raise ValueError("user file must contain a mapping")
                return User(
                    telegram_id=data["telegram_id"],
                    current_model=data.get("current_model"),
                    created_at=data["created_at"],
                )
            except (yaml.YAMLError, ValueError, KeyError) as e:
                logger.warning("user_corrupt", telegram_id=telegram_id, error=str(e))
                return None

    async def save(self, user: User) -> None:
        async with self._lock(user.telegram_id):
            with self._file(user.telegram_id).open("w", encoding="utf-8") as f:
                yaml.safe_dump(asdict(user), f, allow_unicode=True, sort_keys=False)

    async def exists(self, telegram_id: int) -> bool:
        return self._file(telegram_id).exists()
