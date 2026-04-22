"""Fetch OHLCV candle history from Hyperliquid REST API."""

import time
import logging

import httpx
import numpy as np

logger = logging.getLogger(__name__)

INTERVAL_MS = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


async def fetch_candles(interval: str = "1h", limit: int = 300) -> list[dict]:
    """Fetch raw candle dicts from Hyperliquid.

    Returns list of {"t", "o", "h", "l", "c", "v"} dicts, sorted by time.
    Returns empty list on failure.
    """
    ms_per = INTERVAL_MS.get(interval, 3_600_000)
    now = int(time.time() * 1000)
    start = now - (limit * ms_per)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.hyperliquid.xyz/info",
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": interval,
                        "startTime": start,
                        "endTime": now,
                    },
                },
            )
            if resp.status_code == 200:
                raw = resp.json()
                seen = set()
                candles = []
                for c in raw:
                    if c["t"] not in seen:
                        seen.add(c["t"])
                        candles.append(c)
                candles.sort(key=lambda x: x["t"])
                return candles[-limit:]
    except Exception as e:
        logger.error("Failed to fetch %s candles: %s", interval, e)

    return []


def candles_to_arrays(
    candles: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convert raw candle dicts to numpy arrays (opens, highs, lows, closes, volumes)."""
    if not candles:
        empty = np.array([], dtype=float)
        return empty, empty, empty, empty, empty

    opens = np.array([float(c["o"]) for c in candles])
    highs = np.array([float(c["h"]) for c in candles])
    lows = np.array([float(c["l"]) for c in candles])
    closes = np.array([float(c["c"]) for c in candles])
    volumes = np.array([float(c["v"]) for c in candles])
    return opens, highs, lows, closes, volumes


def drop_unclosed(candles: list[dict], interval: str) -> list[dict]:
    """Drop the last candle if its close-time hasn't arrived yet.

    Hyperliquid returns the currently-forming bar as the most recent
    entry in candleSnapshot responses. Using that bar's running OHLC
    values in indicator computation introduces intra-bar leak: RSI,
    MACD, EMA etc. are biased by whatever the price is at fetch time
    instead of using the bar's final close. The backtester uses closed
    bars only (see backtest/simulator.py), so without this helper live
    and backtest disagree on bar-boundary semantics.

    If the last bar's close-time has already passed (rare race when
    fetch lands exactly at bar boundary), it is kept.
    """
    if not candles:
        return candles
    interval_ms = INTERVAL_MS.get(interval, 3_600_000)
    now_ms = int(time.time() * 1000)
    last = candles[-1]
    open_ms = int(last.get("t", 0) or 0)
    if open_ms > 0 and open_ms + interval_ms > now_ms:
        return candles[:-1]
    return candles
