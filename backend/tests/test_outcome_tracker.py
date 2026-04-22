"""Tests for scoring.outcome_tracker — signal outcome resolution."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scoring.outcome_tracker import check_signal_outcomes, get_signal_accuracy


def _mock_signal_row(sig_id, direction, entry_low, entry_high, sl, tp1, tp2, leverage=20):
    """Create a mock Row-like object."""
    data = {
        "id": sig_id,
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
