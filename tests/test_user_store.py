from pathlib import Path

import pytest
import yaml

from app.users import User, UserStore


@pytest.fixture
def users_dir(tmp_path: Path) -> Path:
    return tmp_path / "users"


async def test_load_returns_none_for_unknown_user(users_dir: Path) -> None:
    store = UserStore(users_dir)
    assert await store.load(42) is None


async def test_save_then_load_roundtrip(users_dir: Path) -> None:
    store = UserStore(users_dir)
    user = User(telegram_id=1, current_model="qwen3:0.6b", created_at="2026-04-23T10:00:00")
    await store.save(user)

    loaded = await store.load(1)
    assert loaded == user


async def test_persistence_across_instances(users_dir: Path) -> None:
    s1 = UserStore(users_dir)
    await s1.save(User(telegram_id=7, current_model="gpt-oss-20b", created_at="2026-04-23T10:00:00"))

    s2 = UserStore(users_dir)
    loaded = await s2.load(7)
    assert loaded is not None
    assert loaded.current_model == "gpt-oss-20b"


async def test_per_user_isolation(users_dir: Path) -> None:
    store = UserStore(users_dir)
    await store.save(User(telegram_id=1, current_model="m1", created_at="2026-04-23T10:00:00"))
    await store.save(User(telegram_id=2, current_model="m2", created_at="2026-04-23T10:00:01"))

    u1 = await store.load(1)
    u2 = await store.load(2)
    assert u1 is not None and u1.current_model == "m1"
    assert u2 is not None and u2.current_model == "m2"


async def test_exists(users_dir: Path) -> None:
    store = UserStore(users_dir)
    assert await store.exists(1) is False
    await store.save(User(telegram_id=1, current_model=None, created_at="2026-04-23T10:00:00"))
    assert await store.exists(1) is True


async def test_save_with_none_current_model(users_dir: Path) -> None:
    store = UserStore(users_dir)
    user = User(telegram_id=1, current_model=None, created_at="2026-04-23T10:00:00")
    await store.save(user)

    loaded = await store.load(1)
    assert loaded == user
    assert loaded.current_model is None


async def test_corrupt_yaml_recovers_to_none(users_dir: Path) -> None:
    users_dir.mkdir(parents=True, exist_ok=True)
    (users_dir / "1.yaml").write_text("!!!garbage:::\n- [}\n", encoding="utf-8")

    store = UserStore(users_dir)
    assert await store.load(1) is None


async def test_yaml_format_on_disk(users_dir: Path) -> None:
    store = UserStore(users_dir)
    await store.save(User(telegram_id=99, current_model="qwen3:0.6b", created_at="2026-04-23T10:00:00"))

    on_disk = yaml.safe_load((users_dir / "99.yaml").read_text(encoding="utf-8"))
    assert on_disk == {
        "telegram_id": 99,
        "current_model": "qwen3:0.6b",
        "created_at": "2026-04-23T10:00:00",
    }
