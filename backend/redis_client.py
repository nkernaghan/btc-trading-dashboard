"""Redis client with automatic fallback to in-memory cache.

If Redis is available, uses it. Otherwise falls back to memory_cache.
This means the app works with or without Redis installed.

Also provides staleness tracking helpers: ``set_with_ts`` writes a
sidecar ``{key}:ts`` ISO timestamp alongside the payload, and
``get_fresh`` returns the value only when the sidecar is within the
configured max age for that key. Keys without a policy entry are
always treated as fresh (preserves legacy behavior). WS-driven keys
(btc:price, btc:orderbook, btc:candle:1h, btc:candles:1m:recent) are
deliberately not policied here — they update on every tick, so their
freshness is better judged by the outcome tracker's existing fallback
logic rather than by a scheduler-interval-based cutoff.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_pool = None
_use_memory = None


# Max acceptable age (seconds) per Redis key, set to ~3x the fetcher's
# scheduled interval. A value older than this means the fetcher has
# failed or stalled, and the engine should drop the signal rather than
# vote on a stale number.
_MAX_AGE_SECONDS: dict[str, float] = {
    # 5-minute fetchers -> 15-min cutoff
    "macro:data": 900,
    "coinglass:data": 900,
    "sentiment:btc_dominance": 900,
    "sentiment:polymarket": 900,
    "onchain:data": 900,
    "onchain:stablecoin": 900,
    "news:articles": 900,
    "okx:funding": 900,
    "okx:open_interest": 900,
    "binance:funding": 900,
    "binance:open_interest": 900,
    "coinalyze:liquidations": 900,
    "coinalyze:oi": 900,
    "coinalyze:funding": 900,
    "coinalyze:long_short": 900,
    "onchain:whale_txs": 900,
    # 10-minute fetcher -> 30-min cutoff
    "geopolitical:events": 1800,
    # 15-minute fetchers -> 45-min cutoff
    "onchain:tx_volume": 2700,
    "defi:stablecoin_flows": 2700,
    "defi:tvl": 2700,
    "mining:hashrate": 2700,
    "etf:flows": 2700,
    "sentiment:fear_greed": 2700,
    "options:data": 2700,
    "geopolitical:tone": 2700,
    "geopolitical:conflict": 2700,
}


async def set_with_ts(r, key: str, payload_json: str) -> None:
    """Write a JSON payload plus a sidecar timestamp key.

    The sidecar is ``{key}:ts`` and contains an ISO-8601 UTC timestamp
    of the write. Consumers use it (via ``get_fresh``) to decide
    whether the payload is stale.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    await r.set(key, payload_json)
    await r.set(key + ":ts", now_iso)


async def get_age_seconds(r, key: str) -> float | None:
    """Return the age of ``{key}:ts`` in seconds, or None if missing /
    malformed."""
    ts_raw = await r.get(key + ":ts")
    if not ts_raw:
        return None
    try:
        dt = datetime.fromisoformat(ts_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except (TypeError, ValueError):
        return None


async def is_fresh(r, key: str) -> bool:
    """True if key's sidecar timestamp is within its configured max age.

    Keys without a policy entry return True (considered fresh by
    default). Keys with a policy but no sidecar return False — we
    can't verify freshness, so we treat as stale rather than silently
    vote on an unverifiable value.
    """
    max_age = _MAX_AGE_SECONDS.get(key)
    if max_age is None:
        return True
    age = await get_age_seconds(r, key)
    if age is None:
        return False
    return age <= max_age


async def get_fresh(r, key: str) -> str | None:
    """Return the Redis value for ``key`` only if it's within its
    configured freshness window; else None.

    Drops the read entirely when stale so the engine's existing
    ``if x_raw:`` guards naturally skip the vote — no separate
    dead-code path needed.
    """
    if not await is_fresh(r, key):
        return None
    return await r.get(key)


async def get_redis():
    global _pool, _use_memory

    # First call: try Redis, fall back to memory
    if _use_memory is None:
        if os.environ.get("USE_MEMORY_CACHE", "").lower() in ("1", "true", "yes"):
            _use_memory = True
        else:
            try:
                import redis.asyncio as redis
                from config import settings
                _pool = redis.from_url(settings.redis_url, decode_responses=True)
                await _pool.ping()
                _use_memory = False
                logger.info("Connected to Redis at %s", settings.redis_url)
            except Exception as e:
                logger.warning("Redis unavailable (%s), using in-memory cache", e)
                _use_memory = True
                _pool = None

    if _use_memory:
        from memory_cache import get_redis as get_memory
        return await get_memory()

    return _pool


async def close_redis():
    global _pool, _use_memory
    if _use_memory:
        from memory_cache import close_redis as close_memory
        await close_memory()
    elif _pool:
        await _pool.aclose()
        _pool = None
