"""Push channel for things the user should see as they happen.

The router publishes step progress ("Opening Chrome...") and the reminder
scheduler publishes due reminders. Clients subscribe through the
/api/v1/events Server-Sent Events endpoint.
"""
import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional, Set

logger = logging.getLogger("harika.live_events")


class LiveEventHub:
    MAX_QUEUE = 100

    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def publish(self, event_type: str, **payload: Any) -> None:
        """Safe to call from the event loop or from worker threads."""
        event = {"type": event_type, "time": time.time(), **payload}
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._deliver(event)
        else:
            loop.call_soon_threadsafe(self._deliver, event)

    def _deliver(self, event: Dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            if queue.qsize() >= self.MAX_QUEUE:
                queue.get_nowait()  # a slow client loses its oldest event, not the newest
            queue.put_nowait(event)

    async def stream(self, heartbeat_seconds: float = 15.0) -> AsyncIterator[str]:
        """Server-Sent Events frames for one subscriber."""
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            self._subscribers.discard(queue)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop


live_events = LiveEventHub()
