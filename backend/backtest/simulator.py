"""Walk-forward backtester using technical indicators on historical candles.

Fetches OHLCV candles from Hyperliquid, computes a technical-only signal at
each step of a rolling window, simulates each trade forward to SL/TP
resolution, and feeds the outcomes into the existing backtest engine.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

from backtest.engine import run_backtest_on_signals
from data.candles import fetch_candles, candles_to_arrays
from indicators.technical_analysis import compute_technical_snapshot

logger = logging.getLogger(__name__)


# ── Scoring constants ────────────────────────────────────────────────────────

# RSI bands: oversold / overbought thresholds
_RSI_OVERSOLD = 35.0
_RSI_OVERBOUGHT = 65.0

# ATR multipliers for SL and TP levels
_SL_ATR_MULT = 1.5
_TP1_ATR_MULT = 2.5
_TP2_ATR_MULT = 4.0


def _score_technical_snapshot(snapshot: dict) -> tuple[float, Literal["LONG", "SHORT", "WAIT"]]:
    """Produce a directional score (0-100) from a technical snapshot.

    Scoring logic (technical-only, no macro/sentiment data):
        - RSI contribution  : 30 pts max
        - MACD contribution : 25 pts max
        - EMA alignment     : 25 pts max
        - Structure         : 20 pts max

    Returns:
        score: 0-100 confidence value.
        direction: "LONG", "SHORT", or "WAIT".
    """
    rsi: float = snapshot["rsi"]
    macd_hist: float = snapshot["macd_histogram"]
    ema_aligned: bool = snapshot["ema_aligned"]
    structure: str = snapshot["structure"]
    ema_21: float = snapshot["ema_21"]
    ema_55: float = snapshot["ema_55"]

    # Determine raw directional bias before scoring
    bullish_signals = 0
    bearish_signals = 0

    # RSI
    if rsi < _RSI_OVERSOLD:
        bullish_signals += 1
    elif rsi > _RSI_OVERBOUGHT:
        bearish_signals += 1

    # MACD histogram polarity
    if macd_hist > 0:
        bullish_signals += 1
    elif macd_hist < 0:
        bearish_signals += 1

    # EMA short/long cross
    if ema_21 > ema_55:
        bullish_signals += 1
    elif ema_21 < ema_55:
        bearish_signals += 1

    # Structure
    if structure == "bullish":
        bullish_signals += 1
    elif structure == "bearish":
        bearish_signals += 1

    # No dominant bias → WAIT
    if bullish_signals == bearish_signals:
        return 50.0, "WAIT"

    is_long = bullish_signals > bearish_signals

    # ── RSI contribution (30 pts) ────────────────────────────────────────
    if is_long:
        # Best score when deeply oversold, degrades as RSI approaches 50
        rsi_score = max(0.0, (50.0 - rsi) / (50.0 - _RSI_OVERSOLD)) * 30.0
        # If RSI is already high (>70), penalise — extended, not a good long
        if rsi > 70.0:
            rsi_score = 0.0
    else:
        rsi_score = max(0.0, (rsi - 50.0) / (_RSI_OVERBOUGHT - 50.0)) * 30.0
        if rsi < 30.0:
            rsi_score = 0.0

    # Clamp
    rsi_score = min(30.0, rsi_score)

    # ── MACD contribution (25 pts) ───────────────────────────────────────
    # Use absolute histogram magnitude normalised by a rough scale of 200
    macd_norm = min(abs(macd_hist) / 200.0, 1.0)
    macd_score = macd_norm * 25.0 if (is_long and macd_hist > 0) or (not is_long and macd_hist < 0) else 0.0

    # ── EMA alignment contribution (25 pts) ──────────────────────────────
    ema_score = 25.0 if ema_aligned else 10.0

    # ── Structure contribution (20 pts) ──────────────────────────────────
    if is_long:
        structure_score = 20.0 if structure == "bullish" else (10.0 if structure == "neutral" else 0.0)
    else:
        structure_score = 20.0 if structure == "bearish" else (10.0 if structure == "neutral" else 0.0)

    score = rsi_score + macd_score + ema_score + structure_score
    score = min(100.0, score)

    direction: Literal["LONG", "SHORT"] = "LONG" if is_long else "SHORT"
    return score, direction


def _resolve_trade(
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    future_highs: np.ndarray,
    future_lows: np.ndarray,
) -> float:
    """Scan forward candles bar-by-bar and return the outcome price.

    Checks each bar in order. If the bar's range touches TP1 before SL
    (for LONG: low never drops to SL while high reaches TP1), the trade
    wins at TP1.  Otherwise returns SL if stopped out, or the last close
    approximated as the midpoint of the final bar if hold_bars expires.

    Args:
        direction: "LONG" or "SHORT".
        entry: Trade entry price.
        sl: Stop-loss price.
        tp1: First take-profit price.
        future_highs: Array of high prices for forward bars.
        future_lows: Array of low prices for forward bars.

    Returns:
        outcome_price used by run_backtest_on_signals().
    """
    for high, low in zip(future_highs, future_lows):
        if direction == "LONG":
            # Check SL first (conservative — gives SL priority within a bar)
            if low <= sl:
                return sl
            if high >= tp1:
                return tp1
        else:  # SHORT
            if high >= sl:
                return sl
            if low <= tp1:
                return tp1

    # Neither SL nor TP1 hit — forced exit at midpoint of final bar
    if len(future_highs) > 0:
        return float((future_highs[-1] + future_lows[-1]) / 2.0)
    return entry


async def run_historical_backtest(
    timeframe: str = "1h",
    lookback: int = 2000,
    window: int = 300,
    hold_bars: int = 24,
    min_score: float = 60.0,
) -> dict:
    """Walk-forward backtest using technical indicators on historical candles.

    Args:
        timeframe: Candle interval — "1h", "4h", or "1d".
        lookback: Total number of candles to fetch (max 5000).
        window: Number of trailing candles used to compute each indicator
            snapshot.  Must be < lookback.
        hold_bars: Maximum bars to hold a position before forced exit.
        min_score: Minimum technical score (0-100) required to open a trade.

    Returns:
        Dict from run_backtest_on_signals() with added fields:
            - signals_generated: total walk-forward steps evaluated
            - trades_taken: number of trades that cleared min_score
            - timeframe: the candle interval used
            - lookback: candles fetched
    """
    if window >= lookback:
        logger.warning("window (%d) >= lookback (%d), returning empty result", window, lookback)
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "equity_curve": [10000.0],
            "final_equity": 10000.0,
            "signals_generated": 0,
            "trades_taken": 0,
            "timeframe": timeframe,
            "lookback": lookback,
            "error": "insufficient_candles",
        }

    # ── 1. Fetch candles ─────────────────────────────────────────────────
    candles = await fetch_candles(timeframe, lookback)
    n = len(candles)

    if n < window + hold_bars + 1:
        logger.warning(
            "Insufficient candles: got %d, need at least %d",
            n,
            window + hold_bars + 1,
        )
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "equity_curve": [10000.0],
            "final_equity": 10000.0,
            "signals_generated": 0,
            "trades_taken": 0,
            "timeframe": timeframe,
            "lookback": lookback,
            "error": "insufficient_candles",
        }

    opens, highs, lows, closes, volumes = candles_to_arrays(candles)

    # ── 2. Walk forward ──────────────────────────────────────────────────
    signals_for_engine: list[dict] = []
    signals_generated = 0

    # Start at `window`; we need at least `hold_bars` future bars too
    for i in range(window, n - hold_bars):
        # Trailing window arrays for indicator computation
        w_opens = opens[i - window : i]
        w_highs = highs[i - window : i]
        w_lows = lows[i - window : i]
        w_closes = closes[i - window : i]
        w_volumes = volumes[i - window : i]

        snapshot = compute_technical_snapshot(w_opens, w_highs, w_lows, w_closes, w_volumes)

        score, direction = _score_technical_snapshot(snapshot)
        signals_generated += 1

        if direction == "WAIT" or score < min_score:
            continue

        # ── 3. Build trade parameters ────────────────────────────────────
        entry = float(closes[i])
        atr = snapshot["atr"]

        if atr <= 0:
            continue  # degenerate candle window — skip

        if direction == "LONG":
            sl = entry - _SL_ATR_MULT * atr
            tp1 = entry + _TP1_ATR_MULT * atr
        else:
            sl = entry + _SL_ATR_MULT * atr
            tp1 = entry - _TP1_ATR_MULT * atr

        # ── 4. Simulate forward ──────────────────────────────────────────
        future_slice = slice(i + 1, i + 1 + hold_bars)
        future_highs = highs[future_slice]
        future_lows = lows[future_slice]

        outcome_price = _resolve_trade(
            direction, entry, sl, tp1, future_highs, future_lows
        )

        # Determine leverage from vol_regime (mirrors signal_generator logic)
        vol_regime = snapshot.get("vol_regime", "normal")
        _leverage_map = {
            "low": 35,
            "normal": 25,
            "high": 12,
            "extreme": 3,
        }
        leverage = _leverage_map.get(vol_regime, 25)

        signals_for_engine.append(
            {
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "direction": direction,
                "leverage": leverage,
                "outcome_price": outcome_price,
            }
        )

    # ── 5. Run engine ────────────────────────────────────────────────────
    trades_taken = len(signals_for_engine)

    if trades_taken == 0:
        logger.info(
            "No trades generated (signals_generated=%d, min_score=%.1f)",
            signals_generated,
            min_score,
        )
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "equity_curve": [10000.0],
            "final_equity": 10000.0,
            "signals_generated": signals_generated,
            "trades_taken": 0,
            "timeframe": timeframe,
            "lookback": lookback,
        }

    results = run_backtest_on_signals(signals_for_engine)
    results["signals_generated"] = signals_generated
    results["trades_taken"] = trades_taken
    results["timeframe"] = timeframe
    results["lookback"] = lookback
    return results
