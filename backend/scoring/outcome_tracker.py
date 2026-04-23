"""Signal outcome tracker — checks open signals against recent 1m bars to
determine if TP1, TP2, or SL was hit. Updates the signals table with outcomes.

Uses intra-bar high/low from a rolling window of 1-minute candles cached
by the Hyperliquid WS (`btc:candles:1m:recent`). Checking only the spot
price silently misses wicks that cross SL and recover — the previous
implementation under-reported stop-outs and inflated the win rate.
"""

import json
import logging
from datetime import datetime, timezone

from db import get_db
from redis_client import get_redis

logger = logging.getLogger(__name__)


def _parse_signal_epoch(ts_value) -> int:
    """Best-effort ISO timestamp → epoch seconds. Returns 0 on failure,
    which is interpreted upstream as "no time filter — consider all
    cached bars"."""
    if not ts_value:
        return 0
    try:
        dt = datetime.fromisoformat(str(ts_value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError):
        return 0


def _load_recent_1m_bars(raw: str | None) -> list[dict]:
    """Parse cached 1m bars defensively. Returns [] on any malformed input."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [
        b for b in parsed
        if isinstance(b, dict) and "high" in b and "low" in b and "time" in b
    ]


async def check_signal_outcomes():
    """Check unresolved signals against recent 1m candle high/low.

    For each signal without an outcome:
    - LONG: SL hit if any bar's low <= stop_loss;
            TP hit if any bar's high >= take_profit_N.
    - SHORT: SL hit if any bar's high >= stop_loss;
             TP hit if any bar's low <= take_profit_N.

    SL is checked first so a bar that wicks through both SL and TP1 is
    recorded as SL — mirroring the backtester's conservative convention
    (backtest/simulator.py).

    Bars with `time` earlier than the signal's creation timestamp are
    excluded so a freshly generated signal isn't retroactively closed on
    a wick that occurred before it existed.

    Falls back to spot price (`btc:price`) when the 1m cache is empty or
    malformed — preserves the pre-fix behavior during WS warmup.
    """
    r = await get_redis()

    recent_raw = await r.get("btc:candles:1m:recent")
    recent_bars = _load_recent_1m_bars(recent_raw)

    # Spot-price fallback (also the exit-price reference for logging)
    price_raw = await r.get("btc:price")
    current_price = 0.0
    if price_raw:
        try:
            current_price = float(json.loads(price_raw).get("price", 0) or 0)
        except (TypeError, ValueError):
            current_price = 0.0

    if not recent_bars:
        if current_price <= 0:
            return
        # Synthesize a single "bar" from spot to reuse the same check
        # logic. Time=0 effectively disables the signal-age filter for
        # this degenerate case.
        recent_bars = [{
            "time": 0,
            "open": current_price, "high": current_price,
            "low": current_price, "close": current_price,
            "volume": 0.0,
        }]
    elif current_price <= 0:
        # Use latest bar close as current-price proxy
        current_price = float(recent_bars[-1].get("close", 0) or 0)

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, timestamp, direction, entry_low, entry_high,
                      stop_loss, take_profit_1, take_profit_2,
                      recommended_leverage
               FROM signals
               WHERE outcome IS NULL AND direction IN ('LONG', 'SHORT')
               ORDER BY timestamp DESC LIMIT 50"""
        )
        rows = await cursor.fetchall()

        resolved = 0
        for row in rows:
            sig_id = row["id"]
            direction = row["direction"]
            entry_mid = (row["entry_low"] + row["entry_high"]) / 2
            sl = row["stop_loss"]
            tp1 = row["take_profit_1"]
            tp2 = row["take_profit_2"]
            leverage = row["recommended_leverage"] or 1

            # Exclude bars older than the signal so pre-creation wicks
            # don't retroactively close a fresh signal. _parse_signal_epoch
            # returns 0 on malformed input, which admits all bars.
            signal_ts = _parse_signal_epoch(row["timestamp"])
            relevant = [b for b in recent_bars if b.get("time", 0) >= signal_ts]
            if not relevant:
                # Every cached bar predates the signal — nothing to check
                # yet. Next tracker cycle will see a newer bar.
                continue

            bars_high = max(b["high"] for b in relevant)
            bars_low = min(b["low"] for b in relevant)

            outcome = None
            exit_price = current_price

            if direction == "LONG":
                if bars_low <= sl:
                    outcome = "SL"
                    exit_price = sl
                elif bars_high >= tp2:
                    outcome = "TP2"
                    exit_price = tp2
                elif bars_high >= tp1:
                    outcome = "TP1"
                    exit_price = tp1
            elif direction == "SHORT":
                if bars_high >= sl:
                    outcome = "SL"
                    exit_price = sl
                elif bars_low <= tp2:
                    outcome = "TP2"
                    exit_price = tp2
                elif bars_low <= tp1:
                    outcome = "TP1"
                    exit_price = tp1

            if outcome:
                if direction == "LONG":
                    raw_pct = (exit_price - entry_mid) / entry_mid * 100
                else:
                    raw_pct = (entry_mid - exit_price) / entry_mid * 100

                actual_pnl_pct = raw_pct * leverage
                now = datetime.now(timezone.utc).isoformat()

                await db.execute(
                    """UPDATE signals SET outcome = ?, actual_pnl_pct = ?, closed_at = ?
                       WHERE id = ?""",
                    (outcome, round(actual_pnl_pct, 2), now, sig_id),
                )
                resolved += 1
                logger.info(
                    "Signal #%d resolved: %s → %s (%.2f%% PnL)",
                    sig_id, direction, outcome, actual_pnl_pct,
                )

        if resolved > 0:
            await db.commit()
            logger.info("Resolved %d signal outcomes", resolved)

    finally:
        await db.close()


async def get_signal_accuracy(limit: int = 100) -> dict:
    """Compute signal accuracy stats from resolved signals.

    Returns dict with win_rate, avg_pnl, total_resolved, outcomes breakdown.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT outcome, actual_pnl_pct, direction
               FROM signals
               WHERE outcome IS NOT NULL
               ORDER BY closed_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        return {
            "total_resolved": 0,
            "win_rate": 0.0,
            "avg_pnl_pct": 0.0,
            "outcomes": {"TP1": 0, "TP2": 0, "SL": 0},
        }

    outcomes = {"TP1": 0, "TP2": 0, "SL": 0}
    pnls = []
    for row in rows:
        outcome = row["outcome"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if row["actual_pnl_pct"] is not None:
            pnls.append(row["actual_pnl_pct"])

    wins = outcomes.get("TP1", 0) + outcomes.get("TP2", 0)
    total = len(rows)

    return {
        "total_resolved": total,
        "win_rate": round(wins / total * 100, 1) if total > 0 else 0.0,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "outcomes": outcomes,
    }
