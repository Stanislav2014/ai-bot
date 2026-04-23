from pathlib import Path

import pytest

from app.users.service import UserService
from app.users.store import UserStore


@pytest.fixture
def store(tmp_path: Path) -> UserStore:
    return UserStore(tmp_path / "users")


async def test_get_or_create_creates_new_user(store: UserStore) -> None:
    service = UserService(store, default_model="default-model")
    user = await service.get_or_create(42)

    assert user.telegram_id == 42
    assert user.current_model is None
    assert user.created_at  # ISO timestamp set
    assert await store.exists(42) is True


async def test_get_or_create_returns_existing(store: UserStore) -> None:
    service = UserService(store, default_model="default-model")
    first = await service.get_or_create(42)
    second = await service.get_or_create(42)

    assert first.created_at == second.created_at  # not re-created


async def test_get_model_falls_back_to_default(store: UserStore) -> None:
    service = UserService(store, default_model="default-model")
    assert await service.get_model(42) == "default-model"


async def test_get_model_returns_set_value(store: UserStore) -> None:
    service = UserService(store, default_model="default-model")
    await service.set_model(42, "qwen3:0.6b")

    assert await service.get_model(42) == "qwen3:0.6b"


async def test_set_model_persists_across_instances(store: UserStore, tmp_path: Path) -> None:
    s1 = UserService(store, default_model="default-model")
    await s1.set_model(42, "gpt-oss-20b")

    new_store = UserStore(tmp_path / "users")
    s2 = UserService(new_store, default_model="default-model")
    assert await s2.get_model(42) == "gpt-oss-20b"


async def test_set_model_creates_user_if_missing(store: UserStore) -> None:
    service = UserService(store, default_model="default-model")
    await service.set_model(99, "qwen3:0.6b")

    assert await store.exists(99) is True
    user = await store.load(99)
    assert user is not None
    assert user.current_model == "qwen3:0.6b"
