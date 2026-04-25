from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: Any) -> None:
        for handler in self._subscribers.get(type(event), []):
            await handler(event)
