"""Tests for data.candles — Hyperliquid candle fetcher."""

import numpy as np
import pytest
from unittest.mock import AsyncMock, patch

from data.candles import fetch_candles, candles_to_arrays


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
