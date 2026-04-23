from datetime import datetime, timezone

from app.users.models import User
from app.users.store import UserStore


class UserService:
    def __init__(self, store: UserStore, default_model: str) -> None:
        self._store = store
        self._default_model = default_model

    async def get_or_create(self, telegram_id: int) -> User:
        existing = await self._store.load(telegram_id)
        if existing is not None:
            return existing
        user = User(
            telegram_id=telegram_id,
            current_model=None,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        await self._store.save(user)
        return user

    async def get_model(self, telegram_id: int) -> str:
        user = await self._store.load(telegram_id)
        if user is None or user.current_model is None:
            return self._default_model
        return user.current_model

    async def set_model(self, telegram_id: int, model: str) -> None:
        user = await self.get_or_create(telegram_id)
        user.current_model = model
        await self._store.save(user)
