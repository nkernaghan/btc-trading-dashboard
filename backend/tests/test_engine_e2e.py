"""End-to-end smoke test: engine generates a signal with real technical indicators."""

import json
import pytest
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock


def _make_candle_response(n=200, base=67000.0, trend=0.001):
    np.random.seed(42)
    returns = np.random.normal(trend, 0.005, n)
    closes = base * np.cumprod(1 + returns)
    candles = []
    for i, c in enumerate(closes):
        noise = abs(np.random.normal(0, 50))
        candles.append({
            "t": 1700000000000 + i * 3600000,
            "o": str(round(c - 20, 2)),
            "h": str(round(c + noise, 2)),
            "l": str(round(c - noise, 2)),
            "c": str(round(c, 2)),
            "v": str(round(np.random.uniform(100, 1000), 2)),
        })
    return candles


@pytest.mark.asyncio
async def test_full_signal_generation():
    """Engine produces a valid signal with real technical indicator votes."""
    mock_candles_1h = _make_candle_response(200, trend=0.001)
    mock_candles_4h = _make_candle_response(100, trend=0.001)
    mock_candles_1d = _make_candle_response(100, trend=0.001)

    async def mock_fetch(interval, limit=300):
        if interval == "1h":
            return mock_candles_1h
        elif interval == "4h":
            return mock_candles_4h
        elif interval == "1d":
            return mock_candles_1d
        return []

    stored_signal = {}

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=lambda key: {
        "btc:candle:1h": json.dumps({
            "close": 67000, "open": 66900, "high": 67100,
            "low": 66800, "volume": 500,
        }),
        "btc:orderbook": json.dumps({
            "bids": [{"price": 66990, "size": 1.5}],
            "asks": [{"price": 67010, "size": 1.2}],
            "spread": 20, "mid_price": 67000,
        }),
    }.get(key))

    async def mock_set(key, value):
        if key == "btc:signal:latest":
            stored_signal["data"] = json.loads(value)

    mock_redis.set = mock_set
    mock_redis.publish = AsyncMock()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("engine.get_redis", return_value=mock_redis), \
         patch("engine.fetch_candles", side_effect=mock_fetch), \
         patch("engine.get_db", return_value=mock_db), \
         patch("engine.broadcast_signal", new_callable=AsyncMock):

        from engine import run_engine_cycle
        await run_engine_cycle()

    assert "data" in stored_signal, "No signal was generated"
    sig = stored_signal["data"]

    # Signal should have a direction
    assert sig["direction"] in ("LONG", "SHORT", "WAIT")

    # Votes should include technical indicators
    vote_names = [v["name"] for v in sig["votes"]]
    assert "RSI" in vote_names, f"RSI vote missing. Votes: {vote_names}"
    assert "MACD Hist" in vote_names, f"MACD vote missing. Votes: {vote_names}"

    # Composite score should be a real number
    assert isinstance(sig["composite_score"], (int, float))


@pytest.mark.asyncio
async def test_engine_rsi_not_hardcoded():
    """Verify RSI is computed, not the old hardcoded 55.0."""
    mock_candles = _make_candle_response(200, trend=0.003)  # uptrend -> RSI > 55

    async def mock_fetch(interval, limit=300):
        return mock_candles

    stored_signal = {}
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=lambda key: {
        "btc:candle:1h": json.dumps({
            "close": 67000, "open": 66900, "high": 67100,
            "low": 66800, "volume": 500,
        }),
    }.get(key))

    async def mock_set(key, value):
        if key == "btc:signal:latest":
            stored_signal["data"] = json.loads(value)

    mock_redis.set = mock_set
    mock_redis.publish = AsyncMock()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("engine.get_redis", return_value=mock_redis), \
         patch("engine.fetch_candles", side_effect=mock_fetch), \
         patch("engine.get_db", return_value=mock_db), \
         patch("engine.broadcast_signal", new_callable=AsyncMock):

        from engine import run_engine_cycle
        await run_engine_cycle()

    assert "data" in stored_signal
    rsi_vote = next(v for v in stored_signal["data"]["votes"] if v["name"] == "RSI")
    # With trend=0.003 uptrend, RSI should NOT be exactly 55.0
    assert rsi_vote["value"] != 55.0, "RSI is still hardcoded to 55.0!"
