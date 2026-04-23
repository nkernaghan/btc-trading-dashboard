"""Tests for backend.indicators.market_structure."""

import numpy as np
import pytest

from indicators.market_structure import (
    detect_bos_choch,
    detect_cme_gaps,
    detect_fair_value_gaps,
    detect_order_blocks,
    detect_swing_points,
)


def test_detect_swing_points():
    np.random.seed(42)
    n = 100
    base = np.sin(np.linspace(0, 8 * np.pi, n)) * 500 + 67000
    noise = np.random.normal(0, 20, n)
    highs = base + np.abs(noise) + 50
    lows = base - np.abs(noise) - 50
    sh, sl = detect_swing_points(highs, lows, lookback=2)
    assert len(sh) > 0
    assert len(sl) > 0


def test_detect_bos_bullish():
    # Higher highs and higher lows → bullish BOS
    swing_highs = [67000, 67500, 68000]
    swing_lows = [66000, 66500, 67000]
    result = detect_bos_choch(swing_highs, swing_lows)
    assert result["structure"] == "bullish"


def test_detect_bos_bearish():
    # Lower highs and lower lows → bearish BOS
    swing_highs = [68000, 67500, 67000]
    swing_lows = [67000, 66500, 66000]
    result = detect_bos_choch(swing_highs, swing_lows)
    assert result["structure"] == "bearish"


def test_detect_order_blocks():
    np.random.seed(42)
    n = 50
    opens = np.random.normal(67000, 100, n)
    closes = opens + np.random.normal(0, 150, n)
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 50, n))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 50, n))
    obs = detect_order_blocks(opens, highs, lows, closes)
    assert isinstance(obs, list)
    for ob in obs:
        assert "type" in ob
        assert "high" in ob
        assert "low" in ob


def test_detect_fvg():
    # Create data with clear gaps
    highs = np.array([100, 105, 115, 120, 125])
    lows = np.array([95, 100, 108, 115, 120])
    # FVG at index 2: lows[3]=115 > highs[1]=105 → bullish FVG
    fvgs = detect_fair_value_gaps(highs, lows)
    assert isinstance(fvgs, list)


def test_cme_gaps():
    daily_closes = [
        {"date": "2026-03-28", "close": 67000, "open": 66800},
        {"date": "2026-03-31", "close": 67800, "open": 67500},  # Gap up over weekend
    ]
    gaps = detect_cme_gaps(daily_closes, current_price=67600)
    assert len(gaps) > 0
    assert gaps[0]["direction"] == "up"
