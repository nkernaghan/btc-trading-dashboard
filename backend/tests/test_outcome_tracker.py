"""Tests for scoring.outcome_tracker — signal outcome resolution."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scoring.outcome_tracker import check_signal_outcomes, get_signal_accuracy


def _mock_signal_row(
    sig_id, direction, entry_low, entry_high, sl, tp1, tp2,
    leverage=20, timestamp="1970-01-01T00:00:00+00:00",
):
    """Create a mock Row-like object. Timestamp defaults to epoch 0 so
    the outcome tracker's signal-age filter admits all cached bars."""
    data = {
        "id": sig_id,
        "timestamp": timestamp,
        "direction": direction,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "recommended_leverage": leverage,
    }
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    return row


@pytest.mark.asyncio
async def test_long_sl_hit():
    """LONG signal should resolve as SL when price drops below stop_loss."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"price": 65000}))

    row = _mock_signal_row(1, "LONG", 66900, 67100, 66000, 68500, 70000)
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    # Should have called UPDATE with outcome="SL"
    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1
    args = update_calls[0][0][1]
    assert args[0] == "SL"


@pytest.mark.asyncio
async def test_long_tp1_hit():
    """LONG signal should resolve as TP1 when price rises above take_profit_1."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"price": 69000}))

    row = _mock_signal_row(2, "LONG", 66900, 67100, 66000, 68500, 70000)
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1
    args = update_calls[0][0][1]
    assert args[0] == "TP1"


@pytest.mark.asyncio
async def test_short_sl_hit():
    """SHORT signal should resolve as SL when price rises above stop_loss."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"price": 69000}))

    row = _mock_signal_row(3, "SHORT", 66900, 67100, 68500, 65500, 64000)
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1
    args = update_calls[0][0][1]
    assert args[0] == "SL"


@pytest.mark.asyncio
async def test_no_resolution_when_price_between_sl_tp():
    """Signal should NOT resolve when price is between SL and TP1."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"price": 67500}))

    row = _mock_signal_row(4, "LONG", 66900, 67100, 66000, 68500, 70000)
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    # No UPDATE should have been called
    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 0


@pytest.mark.asyncio
async def test_long_sl_hit_via_1m_wick():
    """SL should resolve when a recent 1m bar's LOW crossed SL even
    though the current spot price has recovered back into range.

    This is the core intra-bar fix: the pre-fix tracker checked only
    current price and would have missed this SL hit entirely.
    """
    recent_bars = [
        {"time": 100, "open": 67000, "high": 67100, "low": 66950,
         "close": 67050, "volume": 1.0},
        # This bar wicked DOWN through SL=66000 and recovered.
        {"time": 160, "open": 67050, "high": 67150, "low": 65800,
         "close": 67200, "volume": 2.5},
        {"time": 220, "open": 67200, "high": 67400, "low": 67150,
         "close": 67350, "volume": 1.2},
    ]

    async def mock_get(key):
        if key == "btc:candles:1m:recent":
            return json.dumps(recent_bars)
        if key == "btc:price":
            return json.dumps({"price": 67350})  # current price back in range
        return None

    mock_redis = AsyncMock()
    mock_redis.get = mock_get

    row = _mock_signal_row(
        5, "LONG", 66900, 67100, 66000, 68500, 70000,
        timestamp="1970-01-01T00:00:00+00:00",  # signal precedes all bars
    )
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1, "expected exactly one UPDATE"
    args = update_calls[0][0][1]
    assert args[0] == "SL", f"expected SL outcome, got {args[0]}"
    # Exit at the SL level (not the wick bottom) — reflects a stop order fill
    # PnL = (66000 - 67000) / 67000 * 100 * 20 = -29.85
    assert args[1] < 0, "SL outcome should produce negative PnL"


@pytest.mark.asyncio
async def test_signal_newer_than_all_bars_is_not_resolved():
    """A signal whose timestamp is AFTER every cached bar must not be
    resolved — no bar postdates its creation, so there's no evidence
    for any outcome yet."""
    recent_bars = [
        {"time": 100, "open": 67000, "high": 67100, "low": 65800,
         "close": 67050, "volume": 1.0},
    ]

    async def mock_get(key):
        if key == "btc:candles:1m:recent":
            return json.dumps(recent_bars)
        if key == "btc:price":
            return json.dumps({"price": 67000})
        return None

    mock_redis = AsyncMock()
    mock_redis.get = mock_get

    # Signal timestamp is far in the future relative to bars at time=100
    row = _mock_signal_row(
        6, "LONG", 66900, 67100, 66000, 68500, 70000,
        timestamp="2099-01-01T00:00:00+00:00",
    )
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 0, "signal newer than all bars must not resolve"


@pytest.mark.asyncio
async def test_resolves_signal_older_than_short_window():
    """Regression for must-fix #4: a signal whose lifetime spans longer
    than the old 10-bar window must still resolve, provided the ring
    buffer is sized to cover it. Seeds 60 bars (1h of 1m data) with the
    SL wick buried ~50 minutes in the past — the pre-fix 10-bar buffer
    would have evicted it before the tracker next ran, silently missing
    the stop-out once spot recovered.
    """
    # 60 bars, times 1_700_000_000 .. +59*60
    base_t = 1_700_000_000
    recent_bars = []
    for i in range(60):
        t = base_t + i * 60
        # Default calm bars around 67000
        bar = {
            "time": t, "open": 67000, "high": 67050, "low": 66950,
            "close": 67000, "volume": 1.0,
        }
        # Put the SL wick in bar index 5 (~50 minutes before the tail)
        if i == 5:
            bar = {
                "time": t, "open": 67000, "high": 67100, "low": 65800,
                "close": 67050, "volume": 2.5,
            }
        recent_bars.append(bar)

    async def mock_get(key):
        if key == "btc:candles:1m:recent":
            return json.dumps(recent_bars)
        if key == "btc:price":
            # Spot has since recovered back into range — pre-fix
            # "check current price" code would see no SL hit.
            return json.dumps({"price": 67350})
        return None

    mock_redis = AsyncMock()
    mock_redis.get = mock_get

    # Signal predates every bar, so the age filter admits them all.
    row = _mock_signal_row(
        7, "LONG", 66900, 67100, 66000, 68500, 70000,
        timestamp="1970-01-01T00:00:00+00:00",
    )
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_redis", return_value=mock_redis), \
         patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        await check_signal_outcomes()

    update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1, "expected SL resolution from older-window wick"
    args = update_calls[0][0][1]
    assert args[0] == "SL", f"expected SL, got {args[0]}"


@pytest.mark.asyncio
async def test_accuracy_empty():
    """Accuracy with no resolved signals should return zeros."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.close = AsyncMock()

    with patch("scoring.outcome_tracker.get_db", return_value=mock_db):
        result = await get_signal_accuracy()

    assert result["total_resolved"] == 0
    assert result["win_rate"] == 0.0
