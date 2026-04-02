"""Main engine: reads data from Redis, computes indicators, generates signals."""
import asyncio
import json
import logging
import numpy as np
from datetime import datetime, timezone

from redis_client import get_redis
from db import get_db
from models.schemas import IndicatorVote, Signal
from models.enums import IndicatorCategory, VoteType, Direction
from indicators.technical import calc_rsi, calc_macd, calc_ema, calc_bollinger_bands, calc_atr
from indicators.order_flow import calc_l4_depth_imbalance
from indicators.volatility import calc_rolling_realized_vol, calc_vol_regime
from indicators.confluence import calc_confluence
from scoring.composite import compute_composite_signal
from scoring.signal_generator import generate_signal
from api.websocket import broadcast_signal

logger = logging.getLogger(__name__)


def vote(name: str, category: IndicatorCategory, value: float, thresholds: dict) -> IndicatorVote:
    """Create a vote from value and thresholds.
    thresholds: {"bull": (low, high), "bear": (low, high)}"""
    bull_range = thresholds.get("bull", (None, None))
    bear_range = thresholds.get("bear", (None, None))

    if bull_range[0] is not None and bull_range[1] is not None:
        if bull_range[0] <= value <= bull_range[1]:
            strength = min(3, int(1 + abs(value - bull_range[0]) / max(1, bull_range[1] - bull_range[0]) * 2))
            return IndicatorVote(name=name, category=category, vote=VoteType.BULL,
                                 strength=strength, value=value, description=f"{name}: {value:.2f}")
    if bear_range[0] is not None and bear_range[1] is not None:
        if bear_range[0] <= value <= bear_range[1]:
            strength = min(3, int(1 + abs(value - bear_range[0]) / max(1, bear_range[1] - bear_range[0]) * 2))
            return IndicatorVote(name=name, category=category, vote=VoteType.BEAR,
                                 strength=strength, value=value, description=f"{name}: {value:.2f}")

    return IndicatorVote(name=name, category=category, vote=VoteType.NEUTRAL,
                         strength=1, value=value, description=f"{name}: {value:.2f}")


async def run_engine_cycle():
    """One full cycle: read data -> compute indicators -> generate signal -> broadcast."""
    r = await get_redis()

    candle_raw = await r.get("btc:candle:1h")
    orderbook_raw = await r.get("btc:orderbook")
    macro_raw = await r.get("macro:data")
    onchain_raw = await r.get("onchain:data")
    fg_raw = await r.get("sentiment:fear_greed")
    options_raw = await r.get("options:data")
    coinglass_raw = await r.get("coinglass:data")

    if not candle_raw:
        return

    candle = json.loads(candle_raw)
    current_price = candle["close"]

    votes: list[IndicatorVote] = []

    # Order Flow
    if orderbook_raw:
        book = json.loads(orderbook_raw)
        depth_imb = calc_l4_depth_imbalance(book.get("bids", []), book.get("asks", []))
        votes.append(vote("OB Depth", IndicatorCategory.ORDER_FLOW, depth_imb,
                          {"bull": (0.1, 1.0), "bear": (-1.0, -0.1)}))
        spread = book.get("spread", 0)
        votes.append(vote("Spread", IndicatorCategory.ORDER_FLOW, spread,
                          {"bull": (0, 5), "bear": (20, 1000)}))

    # Macro/Derivatives
    if macro_raw:
        macro = json.loads(macro_raw)
        if "dxy" in macro:
            dxy_change = macro["dxy"].get("change_pct", 0)
            votes.append(vote("DXY", IndicatorCategory.MACRO_DERIVATIVES, dxy_change,
                              {"bull": (-10, -0.1), "bear": (0.1, 10)}))
        if "spx" in macro:
            spx_change = macro["spx"].get("change_pct", 0)
            votes.append(vote("SPX", IndicatorCategory.MACRO_DERIVATIVES, spx_change,
                              {"bull": (0.1, 10), "bear": (-10, -0.1)}))

    if options_raw:
        options = json.loads(options_raw)
        pc = options.get("put_call_ratio", 1.0)
        votes.append(vote("P/C Ratio", IndicatorCategory.MACRO_DERIVATIVES, pc,
                          {"bull": (0, 0.7), "bear": (1.3, 5.0)}))
        iv = options.get("iv_index", 50)
        votes.append(vote("IV Index", IndicatorCategory.MACRO_DERIVATIVES, iv,
                          {"bear": (80, 200), "bull": (10, 40)}))

    if coinglass_raw:
        cg = json.loads(coinglass_raw)
        if "funding_rates" in cg:
            votes.append(vote("Funding", IndicatorCategory.MACRO_DERIVATIVES, 0.01,
                              {"bull": (-0.1, -0.0001), "bear": (0.0005, 0.1)}))

    # On-Chain
    if onchain_raw:
        onchain = json.loads(onchain_raw)
        if "net_exchange_flow" in onchain:
            flow = onchain["net_exchange_flow"]
            votes.append(vote("Exch Flow", IndicatorCategory.ON_CHAIN, flow,
                              {"bull": (-1e10, -100), "bear": (100, 1e10)}))
        if "mvrv" in onchain:
            mvrv = onchain["mvrv"]
            votes.append(vote("MVRV", IndicatorCategory.ON_CHAIN, mvrv,
                              {"bull": (0.5, 2.0), "bear": (3.5, 10)}))
        if "sopr" in onchain:
            sopr = onchain["sopr"]
            votes.append(vote("SOPR", IndicatorCategory.ON_CHAIN, sopr,
                              {"bull": (0.9, 1.0), "bear": (1.05, 2.0)}))

    # Sentiment
    if fg_raw:
        fg = json.loads(fg_raw)
        fg_val = fg.get("value", 50)
        votes.append(vote("F&G", IndicatorCategory.SENTIMENT, fg_val,
                          {"bull": (10, 35), "bear": (75, 100)}))

    # Composite scoring
    confluence_count = 2
    confluence_bonus = 5
    rsi_val = 55.0
    ema_aligned = True
    structure = "neutral"

    result = compute_composite_signal(
        votes=votes, confluence_count=confluence_count,
        confluence_bonus=confluence_bonus, rsi=rsi_val,
        ema_aligned=ema_aligned, structure=structure,
    )

    atr_val = current_price * 0.007
    vol_regime = "normal"

    signal = generate_signal(
        direction=result["direction"], score=result["score"],
        current_price=current_price, atr=atr_val,
        vol_regime=vol_regime, confluence_count=result["confluence_count"],
        votes=votes, warnings=[],
    )

    # Store + broadcast
    await r.set("btc:signal:latest", signal.model_dump_json())
    await r.set("btc:votes:latest", json.dumps([v.model_dump() for v in votes]))
    await broadcast_signal(signal.model_dump())

    # Log to SQLite
    db = await get_db()
    await db.execute(
        """INSERT INTO signals (timestamp, direction, composite_score, strength,
           entry_low, entry_high, stop_loss, take_profit_1, take_profit_2,
           recommended_leverage, liquidation_price, risk_reward_ratio,
           confluence_count, votes_json, warnings_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (signal.timestamp.isoformat(), signal.direction.value, signal.composite_score,
         signal.strength.value, signal.entry_low, signal.entry_high, signal.stop_loss,
         signal.take_profit_1, signal.take_profit_2, signal.recommended_leverage,
         signal.liquidation_price, signal.risk_reward_ratio, signal.confluence_count,
         json.dumps([v.model_dump() for v in signal.votes]),
         json.dumps(signal.warnings)),
    )
    await db.commit()
    await db.close()

    logger.info(f"Signal: {signal.direction.value} {signal.composite_score:.0f}% -- {len(votes)} votes")


async def engine_loop():
    """Run engine cycle every 60 seconds."""
    while True:
        try:
            await run_engine_cycle()
        except Exception as e:
            logger.error(f"Engine cycle error: {e}")
        await asyncio.sleep(60)
