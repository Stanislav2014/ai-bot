from app.events import (
    EventBus,
    HistoryResetRequested,
    HistorySummarized,
    MessageReceived,
    ResponseGenerated,
)
from app.history.store import HistoryStore


def subscribe(bus: EventBus, store: HistoryStore) -> None:
    """Wire HistoryStore as a subscriber to chat events.

    All write paths into history go through the bus — direct calls live only
    inside this module.
    """

    async def on_message_received(event: MessageReceived) -> None:
        await store.append(event.telegram_id, "user", event.text)

    async def on_response_generated(event: ResponseGenerated) -> None:
        await store.append(event.telegram_id, "assistant", event.text)

    async def on_history_summarized(event: HistorySummarized) -> None:
        await store.replace(event.telegram_id, event.messages)

    async def on_history_reset_requested(event: HistoryResetRequested) -> None:
        await store.reset(event.telegram_id)

    bus.subscribe(MessageReceived, on_message_received)
    bus.subscribe(ResponseGenerated, on_response_generated)
    bus.subscribe(HistorySummarized, on_history_summarized)
    bus.subscribe(HistoryResetRequested, on_history_reset_requested)
