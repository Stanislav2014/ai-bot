from dataclasses import dataclass

import pytest

from app.events import EventBus


@dataclass(frozen=True)
class _EventA:
    payload: str


@dataclass(frozen=True)
class _EventB:
    payload: str


async def test_publish_calls_subscribed_handler() -> None:
    bus = EventBus()
    received: list[_EventA] = []

    async def handler(event: _EventA) -> None:
        received.append(event)

    bus.subscribe(_EventA, handler)
    await bus.publish(_EventA("hi"))

    assert received == [_EventA("hi")]


async def test_multiple_subscribers_called_in_subscription_order() -> None:
    bus = EventBus()
    order: list[str] = []

    async def first(event: _EventA) -> None:
        order.append("first")

    async def second(event: _EventA) -> None:
        order.append("second")

    bus.subscribe(_EventA, first)
    bus.subscribe(_EventA, second)
    await bus.publish(_EventA("x"))

    assert order == ["first", "second"]


async def test_publish_without_subscribers_does_not_raise() -> None:
    bus = EventBus()
    await bus.publish(_EventA("noop"))


async def test_handler_for_other_event_type_not_called() -> None:
    bus = EventBus()
    received_a: list[_EventA] = []
    received_b: list[_EventB] = []

    async def handler_a(event: _EventA) -> None:
        received_a.append(event)

    async def handler_b(event: _EventB) -> None:
        received_b.append(event)

    bus.subscribe(_EventA, handler_a)
    bus.subscribe(_EventB, handler_b)
    await bus.publish(_EventA("only-a"))

    assert received_a == [_EventA("only-a")]
    assert received_b == []


async def test_handler_exception_propagates() -> None:
    bus = EventBus()

    async def bad(event: _EventA) -> None:
        raise RuntimeError("boom")

    bus.subscribe(_EventA, bad)

    with pytest.raises(RuntimeError, match="boom"):
        await bus.publish(_EventA("x"))


async def test_handler_exception_stops_subsequent_handlers() -> None:
    bus = EventBus()
    later_called: list[str] = []

    async def bad(event: _EventA) -> None:
        raise RuntimeError("boom")

    async def later(event: _EventA) -> None:
        later_called.append("ran")

    bus.subscribe(_EventA, bad)
    bus.subscribe(_EventA, later)

    with pytest.raises(RuntimeError):
        await bus.publish(_EventA("x"))

    assert later_called == []  # sequential publish stops on first failure
