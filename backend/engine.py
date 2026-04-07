"""Main engine: reads data from Redis, computes indicators, generates signals."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from redis_client import get_redis
from db import get_db
from models.schemas import IndicatorVote
from models.enums import Direction, IndicatorCategory, VoteType
from indicators.order_flow import calc_l4_depth_imbalance
from indicators.technical_analysis import compute_technical_snapshot
from indicators.confluence import calc_confluence
from data.candles import fetch_candles, candles_to_arrays
from scoring.composite import compute_composite_signal
from scoring.signal_generator import generate_signal
from api.websocket import broadcast_signal
from nlp.sentiment_analyzer import analyze_headlines

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
    geo_tone_raw = await r.get("geopolitical:tone")
    geo_conflict_raw = await r.get("geopolitical:conflict")
    geo_events_raw = await r.get("geopolitical:events")

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
            sentiment = analyze_headlines(articles, max_articles=20)
            if abs(sentiment) > 0.05:  # Only vote if sentiment is meaningful
                votes.append(vote("News Sentiment", IndicatorCategory.SENTIMENT, sentiment,
                                  {"bull": (0.15, 1.0), "bear": (-1.0, -0.15)}))

    if polymarket_raw:
        pm = json.loads(polymarket_raw)
        if isinstance(pm, list) and len(pm) > 0:
            # Just signal that polymarket data exists
            votes.append(vote("Polymarket", IndicatorCategory.SENTIMENT, len(pm),
                              {"bull": (5, 100), "bear": (0, 0)}))  # Neutral placeholder

    # ==================== GEOPOLITICAL (GDELT) — own category ====================
    geo_crisis = False  # tracks if we should gate the signal

    if geo_tone_raw:
        tone = json.loads(geo_tone_raw)
        avg_tone = safe_float(tone.get("avg_tone_24h"), None)
        if avg_tone is not None:
            votes.append(vote("Geo Tone", IndicatorCategory.GEOPOLITICAL, avg_tone,
                              {"bull": (0, 10), "bear": (-10, -2)}))
            if avg_tone < -4:
                warnings.append(f"Geopolitical tension elevated: tone {avg_tone:.1f}")
            if avg_tone < -6:
                geo_crisis = True
                warnings.append("GEOPOLITICAL CRISIS: extreme negative tone — signal weakened")

    if geo_conflict_raw:
        conflict = json.loads(geo_conflict_raw)
        change = safe_float(conflict.get("change_pct"), None)
        if change is not None:
            votes.append(vote("Conflict Vol", IndicatorCategory.GEOPOLITICAL, change,
                              {"bull": (-50, -10), "bear": (20, 200)}))
            if conflict.get("elevated"):
                warnings.append(f"Conflict volume spike: +{change:.0f}%")
            if change > 50:
                geo_crisis = True
                warnings.append("GEOPOLITICAL CRISIS: conflict volume surge — signal weakened")

    if geo_events_raw:
        events = json.loads(geo_events_raw)
        if isinstance(events, list) and len(events) > 0:
            bear_kw = ["war", "attack", "missile", "nuclear", "sanctions", "invasion", "bombing",
                        "escalat", "tariff", "retaliat", "strike", "troops", "mobiliz"]
            bull_kw = ["ceasefire", "peace", "deal", "agreement", "de-escalat", "withdraw", "truce", "diplomac"]
            bear_count = sum(1 for e in events for kw in bear_kw if kw in (e.get("title", "")).lower())
            bull_count = sum(1 for e in events for kw in bull_kw if kw in (e.get("title", "")).lower())
            geo_sentiment = (bull_count - bear_count) / max(bear_count + bull_count, 1)
            votes.append(vote("Geo Events", IndicatorCategory.GEOPOLITICAL, geo_sentiment,
                              {"bull": (0.2, 1.0), "bear": (-1.0, -0.2)}))
            # Trump/tariff-specific detection
            tariff_kw = ["tariff", "trade war", "liberation day", "reciprocal", "import tax", "duties"]
            tariff_hits = sum(1 for e in events for kw in tariff_kw if kw in (e.get("title", "")).lower())
            if tariff_hits >= 3:
                votes.append(vote("Tariff Risk", IndicatorCategory.GEOPOLITICAL, -0.8,
                                  {"bear": (-1.0, -0.3)}))
                warnings.append(f"Tariff headlines dominating ({tariff_hits} mentions)")
                geo_crisis = True

    # ==================== TECHNICAL ANALYSIS (from real candle data) ====================
    h1_candles = await fetch_candles("1h", limit=300)
    h1_arrays = candles_to_arrays(h1_candles)
    h1_opens, h1_highs, h1_lows, h1_closes, h1_volumes = h1_arrays

    if len(h1_closes) >= 15:
        h1_snapshot = compute_technical_snapshot(*h1_arrays)
    else:
        h1_snapshot = {
            "rsi": 50.0, "ema_aligned": True, "structure": "neutral",
            "atr": current_price * 0.007, "vol_regime": "normal",
            "macd_histogram": 0.0, "ema_21": current_price,
            "ema_55": current_price, "ema_200": current_price,
        }

    rsi_val = h1_snapshot["rsi"]
    ema_aligned = h1_snapshot["ema_aligned"]
    structure = h1_snapshot["structure"]
    atr_val = h1_snapshot["atr"]
    vol_regime = h1_snapshot["vol_regime"]

    # Add technical indicator votes
    votes.append(vote("RSI", IndicatorCategory.TECHNICAL, rsi_val,
                       {"bull": (20, 45), "bear": (55, 80)}))
    votes.append(vote("MACD Hist", IndicatorCategory.TECHNICAL, h1_snapshot["macd_histogram"],
                       {"bull": (0.1, 10000), "bear": (-10000, -0.1)}))

    if rsi_val > 80:
        warnings.append(f"RSI overbought at {rsi_val:.1f}")
    elif rsi_val < 20:
        warnings.append(f"RSI oversold at {rsi_val:.1f}")

    if structure != "neutral":
        votes.append(vote("Structure", IndicatorCategory.TECHNICAL, 1.0 if structure == "bullish" else -1.0,
                           {"bull": (0.5, 1.0), "bear": (-1.0, -0.5)}))

    # ==================== MULTI-TIMEFRAME CONFLUENCE ====================
    h4_candles = await fetch_candles("4h", limit=200)
    d1_candles = await fetch_candles("1d", limit=200)

    def _direction_from_snapshot(snap: dict) -> VoteType:
        if snap["rsi"] > 55 and snap["macd_histogram"] > 0:
            return VoteType.BULL
        elif snap["rsi"] < 45 and snap["macd_histogram"] < 0:
            return VoteType.BEAR
        return VoteType.NEUTRAL

    h1_dir = _direction_from_snapshot(h1_snapshot)

    h4_arrays = candles_to_arrays(h4_candles)
    if len(h4_arrays[3]) >= 15:
        h4_snapshot = compute_technical_snapshot(*h4_arrays)
        h4_dir = _direction_from_snapshot(h4_snapshot)
    else:
        h4_dir = VoteType.NEUTRAL

    d1_arrays = candles_to_arrays(d1_candles)
    if len(d1_arrays[3]) >= 15:
        d1_snapshot = compute_technical_snapshot(*d1_arrays)
        d1_dir = _direction_from_snapshot(d1_snapshot)
    else:
        d1_dir = VoteType.NEUTRAL

    confluence_count, confluence_bonus = calc_confluence(h1_dir, h4_dir, d1_dir)

    # ==================== COMPOSITE SCORING ====================
    result = compute_composite_signal(
        votes=votes, confluence_count=confluence_count,
        confluence_bonus=confluence_bonus, rsi=rsi_val,
        ema_aligned=ema_aligned, structure=structure,
    )

    # Geopolitical crisis gate — weakens score and caps leverage during extreme events
    final_score = result["score"]
    final_direction = result["direction"]
    if geo_crisis:
        final_score = final_score * 0.6  # 40% penalty
        if final_score < 50:
            final_direction = Direction.WAIT
        # Force vol_regime to at least "high" during crisis (caps leverage)
        if vol_regime in ("low", "normal"):
            vol_regime = "high"

    signal = generate_signal(
        direction=final_direction, score=final_score,
        current_price=current_price, atr=atr_val,
        vol_regime=vol_regime, confluence_count=result["confluence_count"],
        votes=votes, warnings=warnings,
    )

    # Store + broadcast
    await r.set("btc:signal:latest", signal.model_dump_json())
    await r.set("btc:votes:latest", json.dumps([v.model_dump() for v in votes]))
    await broadcast_signal(json.loads(signal.model_dump_json()))

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
