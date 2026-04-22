"""Signal outcome tracker — checks open signals against current price to determine
if TP1, TP2, or SL was hit. Updates the signals table with outcomes."""

import json
import logging
from datetime import datetime, timezone

from db import get_db
from redis_client import get_redis

logger = logging.getLogger(__name__)


async def check_signal_outcomes():
    """Check all unresolved signals against current price.

    For each signal without an outcome:
    - LONG: SL hit if price <= stop_loss, TP1 hit if price >= take_profit_1,
            TP2 hit if price >= take_profit_2
    - SHORT: SL hit if price >= stop_loss, TP1 hit if price <= take_profit_1,
             TP2 hit if price <= take_profit_2

    Updates the signal row with outcome, actual_pnl_pct, and closed_at.
    """
    r = await get_redis()
    price_raw = await r.get("btc:price")
    if not price_raw:
        return

    price_data = json.loads(price_raw)
    current_price = price_data.get("price", 0)
    if current_price <= 0:
        return

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, direction, entry_low, entry_high, stop_loss,
                      take_profit_1, take_profit_2, recommended_leverage
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

            outcome = None
            exit_price = current_price

            if direction == "LONG":
                if current_price <= sl:
                    outcome = "SL"
                    exit_price = sl
                elif current_price >= tp2:
                    outcome = "TP2"
                    exit_price = tp2
                elif current_price >= tp1:
                    outcome = "TP1"
                    exit_price = tp1
            elif direction == "SHORT":
                if current_price >= sl:
                    outcome = "SL"
                    exit_price = sl
                elif current_price <= tp2:
                    outcome = "TP2"
                    exit_price = tp2
                elif current_price <= tp1:
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
