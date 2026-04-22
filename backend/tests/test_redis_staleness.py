"""Tests for redis_client staleness helpers — set_with_ts, get_fresh,
is_fresh, get_age_seconds."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from redis_client import set_with_ts, is_fresh, get_fresh, get_age_seconds


class _FakeRedis:
    """Minimal dict-backed fake matching the interface used by the helpers."""
    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str):
        self._store[key] = value

    async def get(self, key: str):
        return self._store.get(key)


@pytest.mark.asyncio
async def test_set_with_ts_writes_both_keys():
    r = _FakeRedis()
    await set_with_ts(r, "coinglass:data", '{"hello": "world"}')
    assert await r.get("coinglass:data") == '{"hello": "world"}'
    ts = await r.get("coinglass:data:ts")
    assert ts is not None
    # Round-trips as ISO UTC
    dt = datetime.fromisoformat(ts)
    assert dt.tzinfo is not None


@pytest.mark.asyncio
async def test_is_fresh_true_when_ts_recent():
    r = _FakeRedis()
    await set_with_ts(r, "coinglass:data", "{}")
    assert await is_fresh(r, "coinglass:data") is True


@pytest.mark.asyncio
async def test_is_fresh_false_when_ts_old():
    r = _FakeRedis()
    # Policy for coinglass:data is 900s (15 min); write a ts from 1h ago
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await r.set("coinglass:data", "{}")
    await r.set("coinglass:data:ts", old)
    assert await is_fresh(r, "coinglass:data") is False


@pytest.mark.asyncio
async def test_is_fresh_false_when_ts_missing():
    """A policied key without a sidecar must be treated as stale —
    we can't verify freshness so we drop rather than silently vote."""
    r = _FakeRedis()
    await r.set("coinglass:data", "{}")
    # no :ts written
    assert await is_fresh(r, "coinglass:data") is False


@pytest.mark.asyncio
async def test_is_fresh_true_when_key_unpoliced():
    """Keys without an entry in _MAX_AGE_SECONDS pass unconditionally."""
    r = _FakeRedis()
    assert await is_fresh(r, "unmapped:key") is True


@pytest.mark.asyncio
async def test_get_fresh_returns_value_when_fresh():
    r = _FakeRedis()
    await set_with_ts(r, "options:data", '{"iv": 50}')
    assert await get_fresh(r, "options:data") == '{"iv": 50}'


@pytest.mark.asyncio
async def test_get_fresh_returns_none_when_stale():
    r = _FakeRedis()
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    await r.set("options:data", '{"iv": 50}')
    await r.set("options:data:ts", old)
    assert await get_fresh(r, "options:data") is None


@pytest.mark.asyncio
async def test_get_age_seconds_handles_malformed():
    r = _FakeRedis()
    await r.set("coinglass:data:ts", "not-a-timestamp")
    assert await get_age_seconds(r, "coinglass:data") is None
