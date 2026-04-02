"""Backtest performance metrics."""

from __future__ import annotations

import numpy as np


def calc_sharpe(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio. sqrt(365) annualization for daily returns."""
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    excess = arr - risk_free_rate / 365.0
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(365))


def calc_max_drawdown(equity_curve: list[float]) -> float:
    """Maximum drawdown as negative fraction (e.g., -0.15)."""
    arr = np.array(equity_curve, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    peak = np.maximum.accumulate(arr)
    drawdowns = (arr - peak) / peak
    return float(np.min(drawdowns))


def calc_profit_factor(pnls: list[float]) -> float:
    """Gross profit / gross loss. inf if no losses."""
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    if gross_loss == 0:
        return float("inf")
    return gross_profit / gross_loss


def calc_win_rate(results: list[float]) -> float:
    """Win rate as percentage. Wins = results > 0."""
    if not results:
        return 0.0
    wins = sum(1 for r in results if r > 0)
    return wins / len(results) * 100.0
