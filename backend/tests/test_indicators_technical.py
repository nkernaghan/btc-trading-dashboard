"""Tests for backend.indicators.technical."""

import numpy as np
import pytest

from indicators.technical import (
    calc_atr,
    calc_bollinger_bands,
    calc_ema,
    calc_ichimoku,
    calc_keltner_channels,
    calc_macd,
    calc_rsi,
    calc_stoch_rsi,
    calc_vwap,
    calc_williams_r,
)


# ── helpers ──────────────────────────────────────────────────────────────

def make_prices(n: int = 200, base: float = 67000.0) -> np.ndarray:
    np.random.seed(42)
    returns = np.random.normal(0, 0.005, n)
    prices = base * np.cumprod(1 + returns)
    return prices


@pytest.fixture
def ohlcv():
    np.random.seed(42)
    n = 200
    closes = make_prices(n)
    noise = np.abs(np.random.normal(0, 50, n))
    highs = closes + noise
    lows = closes - noise
    opens = closes + np.random.normal(0, 30, n)
    volumes = np.random.uniform(100, 10000, n)
    return opens, highs, lows, closes, volumes


# ── tests ────────────────────────────────────────────────────────────────

def test_rsi_range():
    prices = make_prices(200)
    rsi = calc_rsi(prices)
    assert 0 <= rsi <= 100


def test_rsi_overbought():
    # Steadily rising prices should push RSI above 70
    prices = np.linspace(60000, 70000, 100)
    rsi = calc_rsi(prices)
    assert rsi > 70


def test_macd_structure():
    prices = make_prices(200)
    macd_line, signal_line, histogram = calc_macd(prices)
    assert abs(histogram - (macd_line - signal_line)) < 1e-6


def test_ema_length():
    prices = make_prices(200)
    ema = calc_ema(prices, 20)
    assert isinstance(ema, float)
    assert 50000 < ema < 90000


def test_bollinger_bands(ohlcv):
    _, _, _, closes, _ = ohlcv
    upper, middle, lower = calc_bollinger_bands(closes)
    assert upper > middle > lower


def test_atr(ohlcv):
    _, highs, lows, closes, _ = ohlcv
    atr = calc_atr(highs, lows, closes)
    assert atr > 0


def test_stoch_rsi():
    prices = make_prices(200)
    k, d = calc_stoch_rsi(prices)
    assert 0 <= k <= 100
    assert 0 <= d <= 100


def test_williams_r(ohlcv):
    _, highs, lows, closes, _ = ohlcv
    wr = calc_williams_r(highs, lows, closes)
    assert -100 <= wr <= 0


def test_vwap(ohlcv):
    _, highs, lows, closes, volumes = ohlcv
    vwap = calc_vwap(highs, lows, closes, volumes)
    assert 50000 < vwap < 90000


def test_keltner_channels(ohlcv):
    _, highs, lows, closes, _ = ohlcv
    upper, middle, lower = calc_keltner_channels(highs, lows, closes)
    assert upper > middle > lower


def test_ichimoku(ohlcv):
    _, highs, lows, closes, _ = ohlcv
    result = calc_ichimoku(highs, lows, closes)
    assert len(result) == 5
    for val in result:
        assert isinstance(val, float)
