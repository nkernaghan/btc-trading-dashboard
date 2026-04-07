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
from indicators.market_structure import detect_cme_gaps

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
    etf_raw = await r.get("etf:flows")
    okx_funding_raw = await r.get("okx:funding")
    okx_oi_raw = await r.get("okx:open_interest")
    binance_funding_raw = await r.get("binance:funding")
    binance_oi_raw = await r.get("binance:open_interest")
    ca_liq_raw = await r.get("coinalyze:liquidations")
    ca_oi_raw = await r.get("coinalyze:oi")
    ca_funding_raw = await r.get("coinalyze:funding")
    ca_ls_raw = await r.get("coinalyze:long_short")
    stablecoin_flows_raw = await r.get("defi:stablecoin_flows")
    defi_tvl_raw = await r.get("defi:tvl")
    hashrate_raw = await r.get("mining:hashrate")
    whale_txs_raw = await r.get("onchain:whale_txs")
    tx_volume_raw = await r.get("onchain:tx_volume")
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
            ("Gold", "Gold", (-10, -0.2), (0.2, 10)),     # Gold up = risk-off = bearish for BTC
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

        max_pain = safe_float(options.get("max_pain_strike"), None)
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

        # net_exchange_flow is currently a proxy (hardcoded 0) — skip until real data source available
        # net_flow = safe_float(onchain.get("net_exchange_flow"), None)

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
        if miner_outflow is not None and miner_outflow > 0:
            # Normalize: typical daily miner revenue is 400-900 BTC
            # Low outflow (<400 BTC) = miners holding = bullish
            # High outflow (>800 BTC) = miners selling = bearish
            votes.append(vote("Miner Outflow", IndicatorCategory.ON_CHAIN, miner_outflow,
                              {"bull": (1, 400), "bear": (800, 5000)}))

        # Outflow/Inflow ratio is currently fake (always 1.0) — skip until real data source available
        # inflow = safe_float(onchain.get("exchange_inflow"), None)
        # outflow = safe_float(onchain.get("exchange_outflow"), None)

    if dominance_raw:
        dom = json.loads(dominance_raw)
        btc_d = safe_float(dom.get("btc_dominance"), None)
        if btc_d is not None:
            votes.append(vote("BTC.D", IndicatorCategory.ON_CHAIN, btc_d,
                              {"bull": (55, 80), "bear": (30, 45)}))

    if stablecoin_raw:
        sc = json.loads(stablecoin_raw)
        usdt_change = safe_float(sc.get("usdt_mcap_change_pct"), None)
        if usdt_change is not None and usdt_change != 0:
            # Growing stablecoin supply = bullish (more buying power entering)
            # Shrinking = bearish (capital leaving)
            votes.append(vote("USDT Supply Chg", IndicatorCategory.ON_CHAIN, usdt_change,
                              {"bull": (0.05, 10), "bear": (-10, -0.05)}))

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
            # Average the "yes" probability across BTC-related prediction markets
            # High avg yes_price on bullish questions = market expects upside
            prices = [m["yes_price"] for m in pm if m.get("yes_price") is not None]
            if prices:
                avg_prob = sum(prices) / len(prices)
                votes.append(vote("Polymarket", IndicatorCategory.SENTIMENT, avg_prob,
                                  {"bull": (0.6, 1.0), "bear": (0.0, 0.4)}))

    # ==================== ETF FLOWS (IBIT/FBTC/GBTC via Yahoo Finance) ====================
    if etf_raw:
        etf = json.loads(etf_raw)
        flow_score = safe_float(etf.get("flow_score"), None)
        etf_vol_ratio = safe_float(etf.get("total_volume_ratio"), None)

        if flow_score is not None:
            # flow_score: -1 (heavy selling) to +1 (heavy buying)
            votes.append(vote("ETF Flow", IndicatorCategory.MACRO_DERIVATIVES, flow_score,
                              {"bull": (0.15, 1.0), "bear": (-1.0, -0.15)}))

        if etf_vol_ratio is not None and etf_vol_ratio > 1.8:
            warnings.append(f"ETF volume spike: {etf_vol_ratio:.1f}x average — institutional activity")

        for e in etf.get("etfs", []):
            if e.get("volume_ratio", 0) > 2.5:
                warnings.append(f"{e['ticker']} volume {e['volume_ratio']:.1f}x avg ({e['price_change_pct']:+.1f}%)")

    # ==================== OKX DERIVATIVES ====================
    if okx_funding_raw:
        okx_f = json.loads(okx_funding_raw)
        okx_avg_rate = safe_float(okx_f.get("avg_rate"), None)
        if okx_avg_rate is not None:
            # Negative funding = shorts paying longs = contrarian bullish
            # High positive funding = crowded longs = bearish
            votes.append(vote("OKX Funding", IndicatorCategory.MACRO_DERIVATIVES, okx_avg_rate,
                              {"bull": (-0.1, -0.0001), "bear": (0.0005, 0.1)}))
            if okx_avg_rate > 0.001:
                warnings.append(f"OKX funding rate elevated: {okx_avg_rate*100:.4f}%")

    if okx_oi_raw:
        okx_oi = json.loads(okx_oi_raw)
        okx_oi_change = safe_float(okx_oi.get("oi_change_pct"), None)
        if okx_oi_change is not None and okx_oi_change != 0:
            # Rising OI with price = trend confirmation (directional from context)
            # Falling OI = positions closing = less conviction
            votes.append(vote("OKX OI Change", IndicatorCategory.MACRO_DERIVATIVES, okx_oi_change,
                              {"bull": (2, 50), "bear": (-50, -2)}))

    # ==================== COINALYZE AGGREGATED DERIVATIVES ====================
    if ca_liq_raw:
        ca_liq = json.loads(ca_liq_raw)
        net_liq = safe_float(ca_liq.get("net_liquidations_usd"), None)
        total_liq = safe_float(ca_liq.get("total_liquidations_usd"), None)
        if net_liq is not None and total_liq is not None and total_liq > 0:
            # Positive net = more longs liquidated = bearish pressure
            # Negative net = more shorts liquidated = bullish pressure
            # Normalize: net / total gives -1 to 1 scale
            liq_ratio = net_liq / total_liq
            votes.append(vote("Liquidations", IndicatorCategory.ORDER_FLOW, liq_ratio,
                              {"bull": (-1.0, -0.2), "bear": (0.2, 1.0)}))
            if total_liq > 50_000_000:  # $50M+ liquidations
                warnings.append(f"Heavy liquidations: ${total_liq/1e6:.0f}M ({ca_liq.get('dominant_side', '?')} dominant)")

    if ca_oi_raw:
        ca_oi = json.loads(ca_oi_raw)
        ca_oi_change = safe_float(ca_oi.get("oi_change_pct"), None)
        if ca_oi_change is not None and ca_oi_change != 0:
            votes.append(vote("Agg OI Change", IndicatorCategory.MACRO_DERIVATIVES, ca_oi_change,
                              {"bull": (2, 50), "bear": (-50, -2)}))

    if ca_funding_raw:
        ca_fund = json.loads(ca_funding_raw)
        ca_rate = safe_float(ca_fund.get("funding_rate"), None)
        if ca_rate is not None:
            votes.append(vote("Agg Funding", IndicatorCategory.MACRO_DERIVATIVES, ca_rate,
                              {"bull": (-0.1, -0.0001), "bear": (0.0005, 0.1)}))

    if ca_ls_raw:
        ca_ls = json.loads(ca_ls_raw)
        ls_ratio = safe_float(ca_ls.get("ratio"), None)
        if ls_ratio is not None:
            # Contrarian: crowded longs (ratio > 1.5) = bearish, crowded shorts (< 0.7) = bullish
            votes.append(vote("Agg L/S Ratio", IndicatorCategory.MACRO_DERIVATIVES, ls_ratio,
                              {"bull": (0.2, 0.7), "bear": (1.5, 5.0)}))

    # ==================== BINANCE DERIVATIVES ====================
    if binance_funding_raw:
        bn_f = json.loads(binance_funding_raw)
        bn_rate = safe_float(bn_f.get("rate"), None)
        if bn_rate is not None:
            # Negative funding = shorts paying longs = contrarian bullish signal
            # High positive funding = overcrowded longs = bearish signal
            votes.append(vote("Binance Funding", IndicatorCategory.MACRO_DERIVATIVES, bn_rate,
                              {"bull": (-0.1, -0.0001), "bear": (0.0005, 0.1)}))
            if bn_rate > 0.001:
                warnings.append(f"Binance funding rate elevated: {bn_rate * 100:.4f}%")

    if binance_oi_raw:
        bn_oi = json.loads(binance_oi_raw)
        bn_oi_change = safe_float(bn_oi.get("oi_change_pct"), None)
        if bn_oi_change is not None:
            # Rising OI = new positions opening = trend confirmation
            # Falling OI = positions unwinding = weakening momentum
            votes.append(vote("Binance OI Change", IndicatorCategory.MACRO_DERIVATIVES, bn_oi_change,
                              {"bull": (2, 50), "bear": (-50, -2)}))

    # ==================== STABLECOIN FLOWS (DeFiLlama) ====================
    if stablecoin_flows_raw:
        sc_flows = json.loads(stablecoin_flows_raw)
        total_1d = safe_float(sc_flows.get("total_1d_change_pct"), None)
        if total_1d is not None and total_1d != 0:
            # Growing stablecoin supply = new capital entering = bullish
            votes.append(vote("Stablecoin Flow", IndicatorCategory.ON_CHAIN, total_1d,
                              {"bull": (0.05, 5), "bear": (-5, -0.05)}))

    # ==================== DEFI TVL ====================
    if defi_tvl_raw:
        tvl = json.loads(defi_tvl_raw)
        tvl_1d = safe_float(tvl.get("tvl_1d_change_pct"), None)
        if tvl_1d is not None and tvl_1d != 0:
            # Rising DeFi TVL = capital flowing into crypto ecosystem = bullish
            votes.append(vote("DeFi TVL", IndicatorCategory.ON_CHAIN, tvl_1d,
                              {"bull": (0.5, 20), "bear": (-20, -0.5)}))

    # ==================== MINING / HASHRATE ====================
    if hashrate_raw:
        mining = json.loads(hashrate_raw)
        hr_change = safe_float(mining.get("hashrate_7d_change_pct"), None)
        if hr_change is not None:
            # Rising hashrate = miners bullish on future profitability
            votes.append(vote("Hashrate", IndicatorCategory.ON_CHAIN, hr_change,
                              {"bull": (2, 50), "bear": (-50, -5)}))

        diff_change = safe_float(mining.get("next_difficulty_change_pct"), None)
        if diff_change is not None and abs(diff_change) > 1:
            # Large upcoming difficulty increase = miners deploying more hardware = bullish
            votes.append(vote("Difficulty Adj", IndicatorCategory.ON_CHAIN, diff_change,
                              {"bull": (3, 30), "bear": (-30, -3)}))

    # ==================== WHALE TRANSACTIONS ====================
    if whale_txs_raw:
        whales = json.loads(whale_txs_raw)
        whale_count = whales.get("whale_tx_count", 0)
        whale_btc = safe_float(whales.get("total_whale_btc"), None)
        if whale_count > 0 and whale_btc is not None:
            # High whale activity during fear = accumulation = bullish
            # High whale activity during greed = distribution = bearish
            # Use count as a raw activity signal — high activity = volatility incoming
            if whale_count >= 5:
                warnings.append(f"Whale activity: {whale_count} txs, {whale_btc:.0f} BTC")

    # ==================== ON-CHAIN TX VOLUME ====================
    if tx_volume_raw:
        tx_vol = json.loads(tx_volume_raw)
        vol_change = safe_float(tx_vol.get("volume_1d_change_pct"), None)
        if vol_change is not None and abs(vol_change) > 5:
            # Surging on-chain volume = increased activity/settlement
            votes.append(vote("On-chain Volume", IndicatorCategory.ON_CHAIN, vol_change,
                              {"bull": (10, 200), "bear": (-200, -10)}))

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

    # ==================== CME GAP DETECTION ====================
    if len(d1_candles) >= 30:
        from datetime import datetime as dt
        daily_closes = []
        for c in d1_candles[-90:]:  # last 90 days
            ts = int(c["t"]) // 1000 if isinstance(c.get("t"), (int, float)) else c.get("time", 0)
            date_str = dt.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
            daily_closes.append({
                "date": date_str,
                "close": float(c.get("c", c.get("close", 0))),
                "open": float(c.get("o", c.get("open", 0))),
            })

        cme_gaps = detect_cme_gaps(daily_closes, current_price)
        unfilled_gaps = [g for g in cme_gaps if not g["filled"]]

        if unfilled_gaps:
            # Find the nearest unfilled gap
            nearest = min(unfilled_gaps, key=lambda g: min(abs(current_price - g["low"]), abs(current_price - g["high"])))
            gap_mid = (nearest["low"] + nearest["high"]) / 2
            gap_dist_pct = (current_price - gap_mid) / current_price * 100

            # CME gaps tend to fill — price is drawn toward them
            # If gap is below: bearish magnet (price likely to drop to fill)
            # If gap is above: bullish magnet (price likely to rise to fill)
            if nearest["direction"] == "up" and current_price > nearest["high"]:
                # Unfilled gap below — bearish gravity
                votes.append(vote("CME Gap Below", IndicatorCategory.TECHNICAL, gap_dist_pct,
                                   {"bear": (0.5, 20)}))
                warnings.append(f"Unfilled CME gap below at ${nearest['low']:,.0f}-${nearest['high']:,.0f} ({nearest['date']})")
            elif nearest["direction"] == "down" and current_price < nearest["low"]:
                # Unfilled gap above — bullish gravity
                votes.append(vote("CME Gap Above", IndicatorCategory.TECHNICAL, abs(gap_dist_pct),
                                   {"bull": (0.5, 20)}))
                warnings.append(f"Unfilled CME gap above at ${nearest['low']:,.0f}-${nearest['high']:,.0f} ({nearest['date']})")

            # Warn if price is inside a gap (partially filled)
            for g in unfilled_gaps:
                if g["low"] <= current_price <= g["high"]:
                    warnings.append(f"Price INSIDE CME gap ${g['low']:,.0f}-${g['high']:,.0f} — likely to complete fill")

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
