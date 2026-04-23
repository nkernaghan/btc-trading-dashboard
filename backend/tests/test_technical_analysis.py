"""Tests for indicators.technical_analysis — high-level analysis from candle arrays."""

import numpy as np
import pytest

from indicators.technical_analysis import compute_technical_snapshot


def _make_ohlcv(n=200, base=67000.0, trend=0.0):
    np.random.seed(42)
    returns = np.random.normal(trend, 0.005, n)
    closes = base * np.cumprod(1 + returns)
    noise = np.abs(np.random.normal(0, 50, n))
    highs = closes + noise
    lows = closes - noise
    opens = closes + np.random.normal(0, 30, n)
    volumes = np.random.uniform(100, 10000, n)
    return opens, highs, lows, closes, volumes


def test_snapshot_returns_all_keys():
    opens, highs, lows, closes, volumes = _make_ohlcv()
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert "rsi" in result
    assert "ema_aligned" in result
    assert "structure" in result
    assert "atr" in result
    assert "vol_regime" in result
    assert "macd_histogram" in result


def test_rsi_in_valid_range():
    opens, highs, lows, closes, volumes = _make_ohlcv()
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert 0 <= result["rsi"] <= 100


def test_uptrend_ema_aligned():
    opens, highs, lows, closes, volumes = _make_ohlcv(n=300, trend=0.003)
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert result["ema_aligned"] is True


def test_structure_values():
    opens, highs, lows, closes, volumes = _make_ohlcv()
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert result["structure"] in ("bullish", "bearish", "neutral")


def test_vol_regime_values():
    opens, highs, lows, closes, volumes = _make_ohlcv()
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert result["vol_regime"] in ("low", "normal", "high", "extreme")


def test_atr_positive():
    opens, highs, lows, closes, volumes = _make_ohlcv()
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert result["atr"] > 0


def test_insufficient_data_returns_defaults():
    opens = np.array([67000.0] * 5)
    highs = opens + 50
    lows = opens - 50
    closes = opens + 10
    volumes = np.ones(5) * 100
    result = compute_technical_snapshot(opens, highs, lows, closes, volumes)
    assert result["rsi"] == 50.0
    assert result["ema_aligned"] is True
    assert result["structure"] == "neutral"
