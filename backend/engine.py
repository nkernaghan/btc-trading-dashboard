"""Main engine: reads data from Redis, computes indicators, generates signals."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from redis_client import get_redis
from db import get_db
from models.schemas import IndicatorVote
from models.enums import IndicatorCategory, VoteType
from indicators.order_flow import calc_l4_depth_imbalance
from scoring.composite import compute_composite_signal
from scoring.signal_generator import generate_signal
from api.websocket import broadcast_signal

logger = logging.getLogger(__name__)


def vote(name: str, category: IndicatorCategory, value: float, thresholds: dict) -> IndicatorVote:
    bull_range = thresholds.get("bull", (None, None))
    bear_range = thresholds.get("bear", (None, None))
    if bull_range[0] is not None and bull_range[1] is not None:
        if bull_range[0] <= value <= bull_range[1]:
            strength = min(3, max(1, int(1 + abs(value - bull_range[0]) / max(0.01, bull_range[1] - bull_range[0]) * 2)))
            return IndicatorVote(name=name, category=category, vote=VoteType.BULL,
                                 strength=strength, value=value, description=f"{name}: {value:.4g}")
    if bear_range[0] is not None and bear_range[1] is not None:
        if bear_range[0] <= value <= bear_range[1]:
            strength = min(3, max(1, int(1 + abs(value - bear_range[0]) / max(0.01, bear_range[1] - bear_range[0]) * 2)))
            return IndicatorVote(name=name, category=category, vote=VoteType.BEAR,
                                 strength=strength, value=value, description=f"{name}: {value:.4g}")
    return IndicatorVote(name=name, category=category, vote=VoteType.NEUTRAL,
                         strength=1, value=value, description=f"{name}: {value:.4g}")


def safe_float(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


async def run_engine_cycle():
    r = await get_redis()

    candle_raw = await r.get("btc:candle:1h")
    orderbook_raw = await r.get("btc:orderbook")
    macro_raw = await r.get("macro:data")
    onchain_raw = await r.get("onchain:data")
    fg_raw = await r.get("sentiment:fear_greed")
    dominance_raw = await r.get("sentiment:btc_dominance")
    polymarket_raw = await r.get("sentiment:polymarket")
    options_raw = await r.get("options:data")
    coinglass_raw = await r.get("coinglass:data")
    stablecoin_raw = await r.get("onchain:stablecoin")
    news_raw = await r.get("news:articles")

    if not candle_raw:
        return

    candle = json.loads(candle_raw)
    current_price = candle["close"]
    votes: list[IndicatorVote] = []
    warnings: list[str] = []

    # ==================== ORDER FLOW ====================
    if orderbook_raw:
        book = json.loads(orderbook_raw)
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if bids and asks:
            depth_imb = calc_l4_depth_imbalance(bids, asks)
            votes.append(vote("OB Depth", IndicatorCategory.ORDER_FLOW, depth_imb,
                              {"bull": (0.1, 1.0), "bear": (-1.0, -0.1)}))

            spread = book.get("spread", 0)
            votes.append(vote("Spread", IndicatorCategory.ORDER_FLOW, spread,
                              {"bull": (0, 5), "bear": (20, 1000)}))

            # Bid depth total vs ask depth total
            bid_depth = sum(b.get("size", 0) for b in bids[:20])
            ask_depth = sum(a.get("size", 0) for a in asks[:20])
            total = bid_depth + ask_depth
            if total > 0:
                ratio = bid_depth / total
                votes.append(vote("Bid/Ask Ratio", IndicatorCategory.ORDER_FLOW, ratio,
                                  {"bull": (0.55, 1.0), "bear": (0.0, 0.45)}))

    # ==================== MACRO / DERIVATIVES ====================
    if macro_raw:
        macro = json.loads(macro_raw)
        for key, label, bull, bear in [
            ("DXY", "DXY", (-10, -0.1), (0.1, 10)),      # DXY down = BTC bullish
            ("SPX", "S&P 500", (0.1, 10), (-10, -0.1)),   # SPX up = BTC bullish
            ("NQ", "Nasdaq", (0.1, 10), (-10, -0.1)),
            ("US10Y", "US 10Y", (-10, -0.05), (0.05, 10)),  # Yields up = bearish
            ("GOLD", "Gold", (-10, -0.2), (0.2, 10)),     # Gold up = risk-off = bearish for BTC
        ]:
            if key in macro:
                change = safe_float(macro[key].get("change_pct"), None)
                if change is not None:
                    votes.append(vote(label, IndicatorCategory.MACRO_DERIVATIVES, change,
                                      {"bull": bull, "bear": bear}))

    if options_raw:
        options = json.loads(options_raw)
        pc = safe_float(options.get("put_call_ratio"), None)
        if pc is not None:
            votes.append(vote("Put/Call", IndicatorCategory.MACRO_DERIVATIVES, pc,
                              {"bull": (0, 0.7), "bear": (1.3, 5.0)}))

        iv = safe_float(options.get("iv_index"), None)
        if iv is not None:
            votes.append(vote("IV Index", IndicatorCategory.MACRO_DERIVATIVES, iv,
                              {"bear": (80, 200), "bull": (10, 40)}))
            if iv > 80:
                warnings.append(f"IV elevated at {iv:.0f}%")

        max_pain = safe_float(options.get("max_pain"), None)
        if max_pain is not None and max_pain > 0:
            dist_to_max_pain = (current_price - max_pain) / max_pain * 100
            votes.append(vote("Max Pain Dist", IndicatorCategory.MACRO_DERIVATIVES, dist_to_max_pain,
                              {"bull": (-20, -2), "bear": (2, 20)}))

    if coinglass_raw:
        cg = json.loads(coinglass_raw)
        # Funding rate
        if "funding_rates" in cg and isinstance(cg["funding_rates"], dict):
            fr = safe_float(cg["funding_rates"].get("rate"), None)
            if fr is not None:
                votes.append(vote("Funding", IndicatorCategory.MACRO_DERIVATIVES, fr,
                                  {"bull": (-0.1, -0.0001), "bear": (0.0005, 0.1)}))
                if fr > 0.0008:
                    warnings.append(f"Funding rate elevated: {fr*100:.4f}%")

        # Long/short ratio
        if "long_short_ratio" in cg and isinstance(cg["long_short_ratio"], dict):
            ls = safe_float(cg["long_short_ratio"].get("ratio"), None)
            if ls is not None:
                votes.append(vote("Long/Short", IndicatorCategory.MACRO_DERIVATIVES, ls,
                                  {"bull": (1.2, 5.0), "bear": (0.2, 0.8)}))

        # Open Interest
        if "open_interest" in cg and isinstance(cg["open_interest"], dict):
            oi_change = safe_float(cg["open_interest"].get("oi_change_24h"), None)
            if oi_change is not None and oi_change != 0:
                votes.append(vote("OI Change", IndicatorCategory.MACRO_DERIVATIVES, oi_change,
                                  {"bull": (1, 50), "bear": (-50, -1)}))

    # ==================== ON-CHAIN ====================
    if onchain_raw:
        onchain = json.loads(onchain_raw)

        net_flow = safe_float(onchain.get("net_exchange_flow"), None)
        if net_flow is not None:
            votes.append(vote("Exch Net Flow", IndicatorCategory.ON_CHAIN, net_flow,
                              {"bull": (-1e10, -100), "bear": (100, 1e10)}))

        mvrv = safe_float(onchain.get("mvrv"), None)
        if mvrv is not None:
            votes.append(vote("MVRV", IndicatorCategory.ON_CHAIN, mvrv,
                              {"bull": (0.5, 2.0), "bear": (3.5, 10)}))
            if mvrv > 3.5:
                warnings.append(f"MVRV overvalued at {mvrv:.2f}")

        sopr = safe_float(onchain.get("sopr"), None)
        if sopr is not None:
            votes.append(vote("SOPR", IndicatorCategory.ON_CHAIN, sopr,
                              {"bull": (0.9, 1.0), "bear": (1.05, 2.0)}))

        miner_outflow = safe_float(onchain.get("miner_outflow"), None)
        if miner_outflow is not None:
            votes.append(vote("Miner Outflow", IndicatorCategory.ON_CHAIN, miner_outflow,
                              {"bull": (0, 0.8), "bear": (1.5, 10)}))

        inflow = safe_float(onchain.get("exchange_inflow"), None)
        outflow = safe_float(onchain.get("exchange_outflow"), None)
        if inflow is not None and outflow is not None and inflow > 0:
            flow_ratio = outflow / inflow
            votes.append(vote("Outflow/Inflow", IndicatorCategory.ON_CHAIN, flow_ratio,
                              {"bull": (1.1, 10), "bear": (0.1, 0.9)}))

    if dominance_raw:
        dom = json.loads(dominance_raw)
        btc_d = safe_float(dom.get("btc_dominance"), None)
        if btc_d is not None:
            votes.append(vote("BTC.D", IndicatorCategory.ON_CHAIN, btc_d,
                              {"bull": (55, 80), "bear": (30, 45)}))

    if stablecoin_raw:
        sc = json.loads(stablecoin_raw)
        usdt_mcap = safe_float(sc.get("usdt_market_cap"), None)
        if usdt_mcap is not None:
            # Growing stablecoin supply = bullish (more buying power)
            votes.append(vote("USDT Supply", IndicatorCategory.ON_CHAIN, usdt_mcap / 1e9,
                              {"bull": (100, 500), "bear": (0, 50)}))

    # ==================== SENTIMENT ====================
    if fg_raw:
        fg = json.loads(fg_raw)
        fg_val = safe_float(fg.get("value"), None)
        if fg_val is not None:
            # Extreme fear = contrarian bullish, extreme greed = contrarian bearish
            votes.append(vote("Fear & Greed", IndicatorCategory.SENTIMENT, fg_val,
                              {"bull": (0, 25), "bear": (75, 100)}))
            if fg_val <= 15:
                warnings.append(f"Extreme Fear: F&G at {fg_val:.0f}")
            elif fg_val >= 85:
                warnings.append(f"Extreme Greed: F&G at {fg_val:.0f}")

    if news_raw:
        articles = json.loads(news_raw)
        if articles and len(articles) > 0:
            # Simple sentiment from news: count bullish vs bearish keywords
            bull_kw = ["surge", "rally", "soar", "bullish", "record", "adoption", "approval", "reserve", "inflow"]
            bear_kw = ["crash", "plunge", "dump", "bearish", "crackdown", "ban", "hack", "liquidation", "tariff", "war"]
            bull_count = 0
            bear_count = 0
            for a in articles[:15]:
                title = (a.get("title") or "").lower()
                bull_count += sum(1 for kw in bull_kw if kw in title)
                bear_count += sum(1 for kw in bear_kw if kw in title)
            total = bull_count + bear_count
            if total > 0:
                sentiment = (bull_count - bear_count) / total  # -1 to +1
                votes.append(vote("News Sentiment", IndicatorCategory.SENTIMENT, sentiment,
                                  {"bull": (0.2, 1.0), "bear": (-1.0, -0.2)}))

    if polymarket_raw:
        pm = json.loads(polymarket_raw)
        if isinstance(pm, list) and len(pm) > 0:
            # Just signal that polymarket data exists
            votes.append(vote("Polymarket", IndicatorCategory.SENTIMENT, len(pm),
                              {"bull": (5, 100), "bear": (0, 0)}))  # Neutral placeholder

    # ==================== COMPOSITE SCORING ====================
    confluence_count = 2
    confluence_bonus = 5
    rsi_val = 55.0  # TODO: compute from actual candle history
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
        votes=votes, warnings=warnings,
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

    logger.info(f"Signal: {signal.direction.value} {signal.composite_score:.0f}% | {len(votes)} votes | {len(warnings)} warnings")


async def engine_loop():
    while True:
        try:
            await run_engine_cycle()
        except Exception as e:
            logger.error(f"Engine cycle error: {e}")
        await asyncio.sleep(60)
