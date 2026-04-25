from pathlib import Path

import pytest

from app.events import (
    EventBus,
    HistoryResetRequested,
    HistorySummarized,
    MessageReceived,
    ResponseGenerated,
)
from app.history import HistoryStore
from app.history.subscriber import subscribe


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "history", max_messages=20)


@pytest.fixture
def bus(store: HistoryStore) -> EventBus:
    bus = EventBus()
    subscribe(bus, store)
    return bus


async def test_message_received_appends_user_message(
    bus: EventBus, store: HistoryStore
) -> None:
    await bus.publish(MessageReceived(telegram_id=1, text="hi"))
    assert await store.get(1) == [{"role": "user", "content": "hi"}]


async def test_response_generated_appends_assistant_message(
    bus: EventBus, store: HistoryStore
) -> None:
    await bus.publish(ResponseGenerated(telegram_id=1, text="hello"))
    assert await store.get(1) == [{"role": "assistant", "content": "hello"}]


async def test_message_then_response_preserves_order(
    bus: EventBus, store: HistoryStore
) -> None:
    await bus.publish(MessageReceived(telegram_id=1, text="hi"))
    await bus.publish(ResponseGenerated(telegram_id=1, text="hello"))
    assert await store.get(1) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


async def test_history_summarized_replaces_history(
    bus: EventBus, store: HistoryStore
) -> None:
    await store.append(1, "user", "old")
    new_msgs = [{"role": "system", "content": "summary"}]
    await bus.publish(HistorySummarized(telegram_id=1, messages=new_msgs))

    assert await store.get(1) == new_msgs


async def test_history_reset_requested_clears_history(
    bus: EventBus, store: HistoryStore
) -> None:
    await store.append(1, "user", "stuff")
    await bus.publish(HistoryResetRequested(telegram_id=1))

    assert await store.get(1) == []


async def test_subscriber_is_per_user_isolated(
    bus: EventBus, store: HistoryStore
) -> None:
    await bus.publish(MessageReceived(telegram_id=1, text="for user 1"))
    await bus.publish(MessageReceived(telegram_id=2, text="for user 2"))

    assert await store.get(1) == [{"role": "user", "content": "for user 1"}]
    assert await store.get(2) == [{"role": "user", "content": "for user 2"}]
