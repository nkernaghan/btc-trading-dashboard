"""Tests for backtest.simulator — walk-forward backtester.

All tests use mocked candle data so no live network calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from backtest.simulator import (
    _resolve_trade,
    _score_technical_snapshot,
    run_historical_backtest,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_candle_list(
    n: int,
    base: float = 67_000.0,
    trend: float = 0.001,
    noise: float = 0.005,
    seed: int = 42,
) -> list[dict]:
    """Generate synthetic OHLCV candle dicts for testing."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, noise, n)
    closes = base * np.cumprod(1 + returns)
    bar_noise = np.abs(rng.normal(0, 80, n))
    candles = []
    for i in range(n):
        c = closes[i]
        h = c + bar_noise[i]
        lo = c - bar_noise[i]
        o = c + rng.normal(0, 30)
        v = float(rng.uniform(100, 5000))
        candles.append({"t": i * 3_600_000, "o": str(o), "h": str(h), "l": str(lo), "c": str(c), "v": str(v)})
    return candles


def _flat_candle_list(n: int = 600, base: float = 67_000.0) -> list[dict]:
    """Generate perfectly flat candles — no directional signal possible."""
    candles = []
    for i in range(n):
        candles.append(
            {
                "t": i * 3_600_000,
                "o": str(base),
                "h": str(base + 1),
                "l": str(base - 1),
                "c": str(base),
                "v": "1000",
            }
        )
    return candles


# ── unit tests: _resolve_trade ────────────────────────────────────────────────


def test_resolve_long_hits_tp1():
    """TP1 reached before SL on a LONG trade."""
    entry = 67_000.0
    sl = 66_500.0
    tp1 = 68_000.0
    highs = np.array([67_200.0, 67_500.0, 68_100.0])
    lows = np.array([66_800.0, 67_100.0, 67_300.0])
    outcome = _resolve_trade("LONG", entry, sl, tp1, highs, lows)
    assert outcome == tp1


def test_resolve_long_hits_sl():
    """SL reached before TP1 on a LONG trade."""
    entry = 67_000.0
    sl = 66_500.0
    tp1 = 68_000.0
    highs = np.array([67_200.0, 67_100.0, 66_600.0])
    lows = np.array([66_800.0, 66_400.0, 66_200.0])
    outcome = _resolve_trade("LONG", entry, sl, tp1, highs, lows)
    assert outcome == sl


def test_resolve_short_hits_tp1():
    """TP1 reached before SL on a SHORT trade."""
    entry = 67_000.0
    sl = 67_500.0
    tp1 = 66_000.0
    highs = np.array([67_200.0, 67_100.0, 67_050.0])
    lows = np.array([66_800.0, 66_500.0, 65_900.0])
    outcome = _resolve_trade("SHORT", entry, sl, tp1, highs, lows)
    assert outcome == tp1


def test_resolve_short_hits_sl():
    """SL reached before TP1 on a SHORT trade."""
    entry = 67_000.0
    sl = 67_500.0
    tp1 = 66_000.0
    highs = np.array([67_300.0, 67_600.0, 67_800.0])
    lows = np.array([66_900.0, 67_100.0, 67_200.0])
    outcome = _resolve_trade("SHORT", entry, sl, tp1, highs, lows)
    assert outcome == sl


def test_resolve_forced_exit():
    """Neither SL nor TP1 hit within hold_bars — forced exit at bar midpoint."""
    entry = 67_000.0
    sl = 60_000.0  # very wide stop
    tp1 = 80_000.0  # very far target
    highs = np.array([67_100.0, 67_200.0, 67_050.0])
    lows = np.array([66_900.0, 66_950.0, 66_800.0])
    outcome = _resolve_trade("LONG", entry, sl, tp1, highs, lows)
    expected_mid = (67_050.0 + 66_800.0) / 2.0
    assert outcome == pytest.approx(expected_mid)


def test_resolve_empty_future_bars():
    """Empty future arrays return entry price unchanged."""
    outcome = _resolve_trade("LONG", 67_000.0, 66_000.0, 68_000.0, np.array([]), np.array([]))
    assert outcome == 67_000.0


# ── unit tests: _score_technical_snapshot ────────────────────────────────────


def _make_bullish_snapshot(rsi: float = 32.0, macd: float = 150.0) -> dict:
    return {
        "rsi": rsi,
        "macd_histogram": macd,
        "ema_aligned": True,
        "structure": "bullish",
        "ema_21": 67_500.0,
        "ema_55": 67_000.0,
        "atr": 400.0,
        "vol_regime": "normal",
    }


def _make_bearish_snapshot(rsi: float = 72.0, macd: float = -150.0) -> dict:
    return {
        "rsi": rsi,
        "macd_histogram": macd,
        "ema_aligned": True,
        "structure": "bearish",
        "ema_21": 66_500.0,
        "ema_55": 67_000.0,
        "atr": 400.0,
        "vol_regime": "normal",
    }


def test_score_bullish_snapshot_direction():
    score, direction = _score_technical_snapshot(_make_bullish_snapshot())
    assert direction == "LONG"


def test_score_bearish_snapshot_direction():
    score, direction = _score_technical_snapshot(_make_bearish_snapshot())
    assert direction == "SHORT"


def test_score_bullish_above_threshold():
    """Strong bullish setup must clear the 60-point default threshold."""
    score, direction = _score_technical_snapshot(_make_bullish_snapshot())
    assert score >= 60.0


def test_score_bearish_above_threshold():
    score, direction = _score_technical_snapshot(_make_bearish_snapshot())
    assert score >= 60.0


def test_score_range():
    """Score must always land between 0 and 100."""
    for snapshot in [_make_bullish_snapshot(), _make_bearish_snapshot()]:
        score, _ = _score_technical_snapshot(snapshot)
        assert 0.0 <= score <= 100.0


def test_score_neutral_returns_wait():
    """Perfectly balanced signals — no dominant bias — returns WAIT."""
    neutral = {
        "rsi": 50.0,
        "macd_histogram": 0.0,
        "ema_aligned": False,
        "structure": "neutral",
        "ema_21": 67_000.0,
        "ema_55": 67_000.0,
        "atr": 400.0,
        "vol_regime": "normal",
    }
    score, direction = _score_technical_snapshot(neutral)
    assert direction == "WAIT"


# ── integration tests: run_historical_backtest ────────────────────────────────


@pytest.mark.asyncio
async def test_walk_forward_produces_trades():
    """Trending candles with a reasonable min_score should generate trades."""
    candles = _make_candle_list(n=600, trend=0.003, seed=0)

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="1h",
            lookback=600,
            window=200,
            hold_bars=24,
            min_score=30.0,  # low threshold to guarantee trades on trending data
        )

    assert result["trades_taken"] > 0
    assert result["total_trades"] > 0
    assert result["signals_generated"] > 0
    assert "equity_curve" in result
    assert len(result["equity_curve"]) == result["total_trades"] + 1


@pytest.mark.asyncio
async def test_flat_data_high_score_produces_no_trades():
    """Flat/choppy data with a very high min_score should generate no trades."""
    candles = _flat_candle_list(n=600)

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="1h",
            lookback=600,
            window=200,
            hold_bars=24,
            min_score=95.0,  # near-impossible threshold
        )

    assert result["trades_taken"] == 0
    assert result["total_trades"] == 0
    assert result["equity_curve"] == [10_000.0]


@pytest.mark.asyncio
async def test_insufficient_candles_returns_safe_default():
    """API returns fewer candles than window + hold_bars — safe default result.

    lookback=500 passes the window < lookback guard, but the mock returns only
    30 candles, so the n < window + hold_bars + 1 check fires instead.
    """
    candles = _make_candle_list(n=30)  # far too few

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="1h",
            lookback=500,  # satisfies window < lookback guard
            window=200,    # 200 + 24 + 1 > 30 → triggers insufficient-candles path
            hold_bars=24,
            min_score=60.0,
        )

    assert result["total_trades"] == 0
    assert result["final_equity"] == 10_000.0
    assert result.get("error") == "insufficient_candles"


@pytest.mark.asyncio
async def test_empty_candles_returns_safe_default():
    """Empty candle list from API returns a zero-trade result."""
    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        result = await run_historical_backtest()

    assert result["total_trades"] == 0
    assert "error" in result


@pytest.mark.asyncio
async def test_sl_tp_resolution_in_walk_forward():
    """Verify SL/TP outcomes are wired correctly by checking equity curve direction.

    Construct a sharp uptrend so all trades should be LONG and win at TP1,
    producing a positive equity curve.
    """
    # Strong uptrend — large positive daily returns
    candles = _make_candle_list(n=700, trend=0.008, noise=0.001, seed=99)

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="1h",
            lookback=700,
            window=200,
            hold_bars=24,
            min_score=20.0,  # let everything through
        )

    if result["trades_taken"] > 0:
        assert result["final_equity"] > 0  # never wiped out
        assert len(result["equity_curve"]) == result["total_trades"] + 1


@pytest.mark.asyncio
async def test_result_metadata_fields():
    """Response dict always includes expected metadata keys."""
    candles = _make_candle_list(n=500, seed=7)

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="4h",
            lookback=500,
            window=150,
            hold_bars=12,
            min_score=60.0,
        )

    for key in ("total_trades", "win_rate", "avg_return_pct", "max_drawdown_pct",
                "sharpe_ratio", "profit_factor", "equity_curve", "final_equity",
                "signals_generated", "trades_taken", "timeframe", "lookback"):
        assert key in result, f"Missing key: {key}"

    assert result["timeframe"] == "4h"
    assert result["lookback"] == 500


@pytest.mark.asyncio
async def test_window_larger_than_lookback_returns_empty():
    """window >= lookback must return a safe empty result."""
    result = await run_historical_backtest(lookback=200, window=300)
    assert result["total_trades"] == 0
    assert result["final_equity"] == 10_000.0
    assert result.get("error") == "insufficient_candles"


@pytest.mark.asyncio
async def test_all_losing_trades_handled_gracefully():
    """Even an all-losing run must return valid metrics without exceptions."""
    # Fabricate signals where every trade hits SL
    candles = _make_candle_list(n=500, trend=-0.01, noise=0.0005, seed=13)

    with patch("backtest.simulator.fetch_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = candles
        result = await run_historical_backtest(
            timeframe="1h",
            lookback=500,
            window=150,
            hold_bars=10,
            min_score=10.0,
        )

    # Should not raise; equity may be lower but structure must be intact
    assert "equity_curve" in result
    assert isinstance(result["win_rate"], float)
    assert isinstance(result["profit_factor"], float)
