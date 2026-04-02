"""Backtesting engine for trade signals."""

from __future__ import annotations

from backtest.metrics import (
    calc_max_drawdown,
    calc_profit_factor,
    calc_sharpe,
    calc_win_rate,
)


def run_backtest_on_signals(
    signals: list[dict], initial_capital: float = 10000
) -> dict:
    """Run backtest on signal outcomes.

    Each signal dict must contain:
        - entry: float        Entry price
        - sl: float           Stop-loss price
        - tp1: float          Take-profit price
        - direction: str      "LONG" or "SHORT"
        - leverage: int|float Leverage multiplier
        - outcome_price: float  The price the trade resolved at

    Logic:
        - Risk 10% of current equity per trade (margin = equity * 0.10)
        - Compute raw PnL percentage based on direction
        - Multiply by leverage (cap losses at -100% of margin)
        - Track equity curve starting with initial_capital

    Returns dict with:
        total_trades, win_rate, avg_return_pct, max_drawdown_pct,
        sharpe_ratio, profit_factor, equity_curve, final_equity
    """
    equity = initial_capital
    equity_curve: list[float] = [equity]
    pnls: list[float] = []
    return_pcts: list[float] = []

    for signal in signals:
        entry = signal["entry"]
        direction = signal["direction"].upper()
        leverage = signal["leverage"]
        outcome_price = signal["outcome_price"]

        # Raw price move as fraction
        if direction == "LONG":
            raw_pct = (outcome_price - entry) / entry
        else:  # SHORT
            raw_pct = (entry - outcome_price) / entry

        # Apply leverage, cap loss at -100% of margin
        leveraged_pct = max(raw_pct * leverage, -1.0)

        # Risk 10% of equity
        margin = equity * 0.10
        trade_pnl = margin * leveraged_pct

        pnls.append(trade_pnl)
        return_pcts.append(leveraged_pct)

        equity += trade_pnl
        equity_curve.append(equity)

    total_trades = len(signals)
    win_rate = calc_win_rate(pnls)
    avg_return_pct = (
        sum(return_pcts) / len(return_pcts) * 100 if return_pcts else 0.0
    )
    max_drawdown_pct = calc_max_drawdown(equity_curve) * 100
    sharpe_ratio = calc_sharpe(return_pcts) if return_pcts else 0.0
    profit_factor = calc_profit_factor(pnls) if pnls else 0.0

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_return_pct": avg_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": sharpe_ratio,
        "profit_factor": profit_factor,
        "equity_curve": equity_curve,
        "final_equity": equity,
    }
