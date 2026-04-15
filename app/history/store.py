import asyncio
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()


class HistoryStore:
    def __init__(self, data_dir: Path, max_messages: int) -> None:
        self._data_dir = data_dir
        self._max_messages = max_messages
        self._cache: dict[int, list[dict[str, str]]] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def _file(self, user_id: int) -> Path:
        return self._data_dir / f"{user_id}.yaml"

    def _load_from_disk(self, user_id: int) -> list[dict[str, str]]:
        path = self._file(user_id)
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                raise ValueError("history file must contain a list")
            return data
        except (yaml.YAMLError, ValueError) as e:
            logger.warning("history_corrupt", user_id=user_id, error=str(e))
            path.write_text("[]\n", encoding="utf-8")
            return []

    async def get(self, user_id: int) -> list[dict[str, str]]:
        async with self._lock(user_id):
            if user_id not in self._cache:
                self._cache[user_id] = self._load_from_disk(user_id)
            return list(self._cache[user_id])
