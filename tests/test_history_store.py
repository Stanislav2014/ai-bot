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


async def test_char_limit_trims_oldest_when_over_budget(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20, max_chars=50)
    for i in range(10):
        await store.append(1, "user", f"m{i:08d}")  # each content is 9 chars
    result = await store.get(1)
    total = sum(len(m["content"]) for m in result)
    assert total <= 50
    assert result[-1]["content"] == "m00000009"
    # Trim stopped at smallest allowable — removing one more would go further
    # but adding one more dropped message would push us back over budget
    assert total + 9 > 50


async def test_char_limit_zero_means_disabled(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=200, max_chars=0)
    long_msg = "x" * 1000
    for _ in range(50):
        await store.append(1, "user", long_msg)
    result = await store.get(1)
    assert len(result) == 50


async def test_char_limit_keeps_last_when_single_message_over_budget(
    history_dir: Path,
) -> None:
    store = HistoryStore(history_dir, max_messages=20, max_chars=10)
    huge = "x" * 100
    await store.append(1, "user", huge)
    result = await store.get(1)
    assert len(result) == 1
    assert result[0]["content"] == huge


async def test_char_and_count_limits_combined(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=5, max_chars=100)
    for _ in range(10):
        await store.append(1, "user", "x" * 30)
    result = await store.get(1)
    # count-trim leaves 5 (150 chars); char-trim drops until <= 100 → 3 × 30 = 90
    assert len(result) == 3
    assert sum(len(m["content"]) for m in result) == 90


async def test_replace_overwrites_cache_and_file(history_dir: Path) -> None:
    store = HistoryStore(history_dir, max_messages=20)
    await store.append(1, "user", "old")
    new_history = [
        {"role": "system", "content": "Summary X"},
        {"role": "user", "content": "latest"},
    ]
    await store.replace(1, new_history)
    assert await store.get(1) == new_history
    s2 = HistoryStore(history_dir, max_messages=20)
    assert await s2.get(1) == new_history
