"""In-memory cache that mimics the Redis interface used by the app.

Drop-in replacement for redis_client.py when Redis is not available.
Supports get, set, publish, and pubsub subscribe/listen.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_store: dict[str, str] = {}
_subscribers: dict[str, list[asyncio.Queue]] = {}


class PubSub:
    """Minimal pubsub that mimics redis.asyncio pubsub interface."""

    def __init__(self):
        self._channels: list[str] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    async def subscribe(self, *channels: str):
        for ch in channels:
            self._channels.append(ch)
            if ch not in _subscribers:
                _subscribers[ch] = []
            _subscribers[ch].append(self._queue)

    async def listen(self):
        while True:
            msg = await self._queue.get()
            yield msg

    async def unsubscribe(self, *channels: str):
        for ch in channels:
            if ch in self._channels:
                self._channels.remove(ch)
            if ch in _subscribers and self._queue in _subscribers[ch]:
                _subscribers[ch].remove(self._queue)


class MemoryCache:
    """In-memory key-value store with pubsub, matching redis.asyncio interface."""

    async def get(self, key: str) -> str | None:
        return _store.get(key)

    async def set(self, key: str, value: str):
        _store[key] = value

    async def publish(self, channel: str, data: str):
        if channel in _subscribers:
            msg = {"type": "message", "channel": channel, "data": data}
            for queue in _subscribers[channel]:
                try:
                    queue.put_nowait(msg)
                except asyncio.QueueFull:
                    pass  # drop message if consumer is slow

    def pubsub(self) -> PubSub:
        return PubSub()

    async def aclose(self):
        _store.clear()
        _subscribers.clear()


_instance: MemoryCache | None = None


async def get_redis() -> MemoryCache:
    """Drop-in replacement for redis_client.get_redis()."""
    global _instance
    if _instance is None:
        _instance = MemoryCache()
    return _instance


async def close_redis():
    """Drop-in replacement for redis_client.close_redis()."""
    global _instance
    if _instance:
        await _instance.aclose()
        _instance = None
