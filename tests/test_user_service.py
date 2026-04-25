from pathlib import Path

import pytest

from app.events import EventBus, UserCreated
from app.users.service import UserService
from app.users.store import UserStore


@pytest.fixture
def store(tmp_path: Path) -> UserStore:
    return UserStore(tmp_path / "users")


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


async def test_get_or_create_creates_new_user(store: UserStore, bus: EventBus) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    user = await service.get_or_create(42)

    assert user.telegram_id == 42
    assert user.current_model is None
    assert user.created_at  # ISO timestamp set
    assert await store.exists(42) is True


async def test_get_or_create_returns_existing(store: UserStore, bus: EventBus) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    first = await service.get_or_create(42)
    second = await service.get_or_create(42)

    assert first.created_at == second.created_at  # not re-created


async def test_get_model_falls_back_to_default(store: UserStore, bus: EventBus) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    assert await service.get_model(42) == "default-model"


async def test_get_model_returns_set_value(store: UserStore, bus: EventBus) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    await service.set_model(42, "qwen3:0.6b")

    assert await service.get_model(42) == "qwen3:0.6b"


async def test_set_model_persists_across_instances(
    store: UserStore, bus: EventBus, tmp_path: Path
) -> None:
    s1 = UserService(store, default_model="default-model", bus=bus)
    await s1.set_model(42, "gpt-oss-20b")

    new_store = UserStore(tmp_path / "users")
    s2 = UserService(new_store, default_model="default-model", bus=EventBus())
    assert await s2.get_model(42) == "gpt-oss-20b"


async def test_set_model_creates_user_if_missing(store: UserStore, bus: EventBus) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    await service.set_model(99, "qwen3:0.6b")

    assert await store.exists(99) is True
    user = await store.load(99)
    assert user is not None
    assert user.current_model == "qwen3:0.6b"


async def test_get_or_create_publishes_user_created_for_new(
    store: UserStore, bus: EventBus
) -> None:
    received: list[UserCreated] = []

    async def handler(event: UserCreated) -> None:
        received.append(event)

    bus.subscribe(UserCreated, handler)
    service = UserService(store, default_model="default-model", bus=bus)

    user = await service.get_or_create(42)

    assert received == [UserCreated(telegram_id=42, created_at=user.created_at)]


async def test_get_or_create_does_not_publish_for_existing(
    store: UserStore, bus: EventBus
) -> None:
    service = UserService(store, default_model="default-model", bus=bus)
    await service.get_or_create(42)  # warm-up: created

    received: list[UserCreated] = []

    async def handler(event: UserCreated) -> None:
        received.append(event)

    bus.subscribe(UserCreated, handler)

    await service.get_or_create(42)  # second call — existing
    assert received == []


async def test_set_model_publishes_user_created_when_user_is_new(
    store: UserStore, bus: EventBus
) -> None:
    received: list[UserCreated] = []

    async def handler(event: UserCreated) -> None:
        received.append(event)

    bus.subscribe(UserCreated, handler)
    service = UserService(store, default_model="default-model", bus=bus)

    await service.set_model(99, "qwen3:0.6b")
    assert len(received) == 1
    assert received[0].telegram_id == 99
