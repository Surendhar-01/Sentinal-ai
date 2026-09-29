import asyncio
from collections import deque


class EventBus:
    def __init__(self, history: int = 100):
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque = deque(maxlen=history)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        for event in list(self._history):
            queue.put_nowait(event)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict) -> dict:
        self._history.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)
        return event

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
