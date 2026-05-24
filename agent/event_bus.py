from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from schemas.python.events import Event


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    @asynccontextmanager
    async def subscribe(self, max_queue_size: int = 100) -> AsyncIterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event: Event) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)


event_bus = InMemoryEventBus()
