"""Tests for backend.indicators.volatility."""

import numpy as np
import pytest

from indicators.volatility import (
    calc_garch_forecast,
    calc_rolling_realized_vol,
    calc_vol_regime,
)


def test_garch_forecast():
    np.random.seed(42)
    prices = 67000 * np.cumprod(1 + np.random.normal(0, 0.01, 500))
    returns = np.diff(np.log(prices))
    vol = calc_garch_forecast(returns)
    assert vol > 0
    assert vol < 5.0  # annualized vol should be well under 500%


def test_rolling_realized_vol():
    np.random.seed(42)
    prices = 67000 * np.cumprod(1 + np.random.normal(0, 0.005, 100))
    vol = calc_rolling_realized_vol(prices, window=24)
    assert vol > 0


def test_vol_regime_low():
    history = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]
    result = calc_vol_regime(0.05, history)
    assert result == "low"


def test_vol_regime_extreme():
    history = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]
    result = calc_vol_regime(0.95, history)
    assert result == "extreme"
