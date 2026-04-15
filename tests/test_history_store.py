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


async def test_window_trims_when_over_limit(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=4)
    for i in range(6):
        await store.append(1, "user", f"m{i}")
    result = await store.get(1)
    assert len(result) == 4
    assert result[0]["content"] == "m2"
    assert result[-1]["content"] == "m5"


async def test_window_zero_means_unlimited(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=0)
    for i in range(50):
        await store.append(1, "user", f"m{i}")
    assert len(await store.get(1)) == 50


async def test_reset_clears_file(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "hi")
    await store.reset(1)
    assert await store.get(1) == []
    assert not (history_dir / "1.yaml").exists()


async def test_corrupt_yaml_recovers(history_dir: Path) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "1.yaml").write_text("!!!garbage:::\n- [}\n", encoding="utf-8")
    store = HistoryStore(history_dir, max_messages=20)
    assert await store.get(1) == []


async def test_per_user_isolation(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "from 1")
    await store.append(2, "user", "from 2")
    assert await store.get(1) == [{"role": "user", "content": "from 1"}]
    assert await store.get(2) == [{"role": "user", "content": "from 2"}]
