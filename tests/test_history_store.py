from pathlib import Path

import pytest

from app.history import HistoryStore


@pytest.fixture
def history_dir(tmp_path: Path) -> Path:
    return tmp_path / "history"


async def test_get_empty_user(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    assert await store.get(1) == []


async def test_append_and_get(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "hi")
    await store.append(1, "assistant", "hello")
    assert await store.get(1) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


async def test_persistence_across_instances(history_dir: Path) -> None:
    s1 = HistoryStore(history_dir, max_messages=20)
    await s1.append(1, "user", "persistent")
    s2 = HistoryStore(history_dir, max_messages=20)
    assert await s2.get(1) == [{"role": "user", "content": "persistent"}]
