import asyncio
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()


def _total_chars(history: list[dict[str, str]]) -> int:
    return sum(len(m["content"]) for m in history)


class HistoryStore:
    def __init__(self, data_dir: Path, max_messages: int, max_chars: int = 0) -> None:
        self._data_dir = data_dir
        self._max_messages = max_messages
        self._max_chars = max_chars
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

    async def append(self, user_id: int, role: str, content: str) -> None:
        async with self._lock(user_id):
            if user_id not in self._cache:
                self._cache[user_id] = self._load_from_disk(user_id)
            history = self._cache[user_id]
            history.append({"role": role, "content": content})
            if self._max_messages > 0 and len(history) > self._max_messages:
                history = history[-self._max_messages :]
            if self._max_chars > 0:
                while len(history) > 1 and _total_chars(history) > self._max_chars:
                    history = history[1:]
            self._cache[user_id] = history
            with self._file(user_id).open("w", encoding="utf-8") as f:
                yaml.safe_dump(history, f, allow_unicode=True, sort_keys=False)

    async def reset(self, user_id: int) -> None:
        async with self._lock(user_id):
            self._cache.pop(user_id, None)
            path = self._file(user_id)
            if path.exists():
                path.unlink()
