"""Tests for data.candles — Hyperliquid candle fetcher."""

import time

import numpy as np
import pytest
from unittest.mock import AsyncMock, patch

from data.candles import fetch_candles, candles_to_arrays, drop_unclosed


def test_candles_to_arrays_basic():
    candles = [
        {"t": 1000000, "o": "67000", "h": "67500", "l": "66500", "c": "67200", "v": "100"},
        {"t": 2000000, "o": "67200", "h": "67800", "l": "67000", "c": "67600", "v": "150"},
    ]
    opens, highs, lows, closes, volumes = candles_to_arrays(candles)
    assert len(closes) == 2
    assert closes[0] == 67200.0
    assert closes[1] == 67600.0
    assert isinstance(opens, np.ndarray)


def test_candles_to_arrays_empty():
    opens, highs, lows, closes, volumes = candles_to_arrays([])
    assert len(closes) == 0


@pytest.mark.asyncio
async def test_fetch_candles_success():
    mock_candles = [
        {"t": 1000000, "o": "67000", "h": "67500", "l": "66500", "c": "67200", "v": "100"},
        {"t": 2000000, "o": "67200", "h": "67800", "l": "67000", "c": "67600", "v": "150"},
    ]
    mock_response = AsyncMock()
    mock_response.status_code = 200
    # json() is a regular method on httpx Response, not async
    from unittest.mock import MagicMock
    mock_response.json = MagicMock(return_value=mock_candles)

    with patch("data.candles.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await fetch_candles("1h", limit=200)
        assert len(result) == 2
        assert result[0]["t"] == 1000000


def test_drop_unclosed_drops_forming_bar():
    """A bar whose open_time + interval is in the future must be dropped."""
    now_ms = int(time.time() * 1000)
    closed_bar = {"t": now_ms - 2 * 3_600_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    forming_bar = {"t": now_ms - 1000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    result = drop_unclosed([closed_bar, forming_bar], "1h")
    assert len(result) == 1
    assert result[0]["t"] == closed_bar["t"]


def test_drop_unclosed_keeps_just_closed_bar():
    """A bar whose close moment has just passed should be kept."""
    now_ms = int(time.time() * 1000)
    # Bar that opened 1h and 5s ago -> close_time = 5s ago -> closed
    bar = {"t": now_ms - 3_600_000 - 5_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    result = drop_unclosed([bar], "1h")
    assert len(result) == 1


def test_drop_unclosed_empty_list():
    assert drop_unclosed([], "1h") == []


def test_drop_unclosed_missing_t_is_not_dropped():
    """A bar with missing / zero `t` can't be classified, so it's kept."""
    bar = {"t": 0, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    assert drop_unclosed([bar], "1h") == [bar]


def test_drop_unclosed_unknown_interval_defaults_to_1h():
    """Unknown interval falls back to 1h (3_600_000 ms)."""
    now_ms = int(time.time() * 1000)
    forming = {"t": now_ms - 1000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    result = drop_unclosed([forming], "15s")
    assert len(result) == 0


def test_drop_unclosed_exact_boundary_keeps_bar():
    """A bar whose close_time == now exactly is KEPT (condition is strict >).

    Lock in the strict-greater-than semantics: the moment a bar closes,
    it stops being "forming" and becomes eligible for indicator use.
    """
    pinned_now_ms = 1_700_000_000_000  # fixed epoch — avoids clock-race flakiness
    # Bar opened exactly 1h ago → close_time = now
    bar = {"t": pinned_now_ms - 3_600_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    with patch("data.candles.time.time", return_value=pinned_now_ms / 1000):
        result = drop_unclosed([bar], "1h")
    assert result == [bar], "bar with close_time == now must be kept"


def test_drop_unclosed_4h_drops_forming_bar():
    """A 4h bar opened 1min ago (still forming) must be dropped."""
    now_ms = int(time.time() * 1000)
    forming = {"t": now_ms - 60_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    assert drop_unclosed([forming], "4h") == []


def test_drop_unclosed_4h_keeps_closed_bar():
    """A 4h bar opened 4h+10s ago (closed) must be kept."""
    now_ms = int(time.time() * 1000)
    closed = {"t": now_ms - 4 * 3_600_000 - 10_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    assert drop_unclosed([closed], "4h") == [closed]


def test_drop_unclosed_1d_drops_forming_bar():
    """A 1d bar opened 1h ago (still forming) must be dropped."""
    now_ms = int(time.time() * 1000)
    forming = {"t": now_ms - 3_600_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    assert drop_unclosed([forming], "1d") == []


def test_drop_unclosed_1d_keeps_closed_bar():
    """A 1d bar opened 24h+10s ago (closed) must be kept."""
    now_ms = int(time.time() * 1000)
    closed = {"t": now_ms - 86_400_000 - 10_000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "0"}
    assert drop_unclosed([closed], "1d") == [closed]


@pytest.mark.asyncio
async def test_fetch_candles_failure_returns_empty():
    with patch("data.candles.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.side_effect = Exception("connection failed")
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await fetch_candles("1h", limit=200)
        assert result == []
