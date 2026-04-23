"""Tests for backtest engine and metrics."""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from backtest.metrics import calc_sharpe, calc_max_drawdown, calc_profit_factor, calc_win_rate
from backtest.engine import run_backtest_on_signals


def test_sharpe_ratio():
    returns = [0.02, -0.01, 0.03, 0.01, -0.005, 0.015, 0.02]
    assert calc_sharpe(returns) > 0


def test_max_drawdown():
    equity = [100, 105, 103, 108, 102, 110, 107, 115]
    dd = calc_max_drawdown(equity)
    assert dd < 0 and dd > -0.1


def test_profit_factor():
    pnls = [100, 200, 150, -50, -75, -60]
    assert calc_profit_factor(pnls) > 1


def test_win_rate():
    results = [1, 1, -1, 1, -1, 1, 1]
    assert calc_win_rate(results) == pytest.approx(5 / 7 * 100, abs=0.1)


def test_run_backtest():
    signals = [
        {
            "entry": 67000,
            "sl": 66500,
            "tp1": 67750,
            "direction": "LONG",
            "leverage": 25,
            "outcome_price": 67800,
        },
        {
            "entry": 68000,
            "sl": 68500,
            "tp1": 67250,
            "direction": "SHORT",
            "leverage": 20,
            "outcome_price": 67200,
        },
        {
            "entry": 67500,
            "sl": 67000,
            "tp1": 68250,
            "direction": "LONG",
            "leverage": 25,
            "outcome_price": 66900,
        },
    ]
    result = run_backtest_on_signals(signals, initial_capital=10000)
    assert result["total_trades"] == 3
    assert len(result["equity_curve"]) == 4
