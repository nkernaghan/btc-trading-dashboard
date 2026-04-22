"""BTC ETF flow proxy — tracks IBIT, FBTC, GBTC volume and price action.

Uses Yahoo Finance (free, no key). Volume relative to 30-day average
combined with price direction approximates institutional flow sentiment.

High volume + price up = institutional buying (bullish)
High volume + price down = institutional selling (bearish)
Low volume = no conviction either way
"""

import json
import logging

import httpx

from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
ETF_TICKERS = ["IBIT", "FBTC", "GBTC"]
HEADERS = {"User-Agent": "Mozilla/5.0"}


async def _fetch_etf_data(client: httpx.AsyncClient, ticker: str) -> dict | None:
    """Fetch 30 days of daily data for a single ETF ticker."""
    try:
        resp = await client.get(
            f"{YAHOO_CHART}/{ticker}",
            params={"interval": "1d", "range": "30d"},
            headers=HEADERS,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        timestamps = result.get("timestamp", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        if not closes or not volumes or len(closes) < 5:
            return None

        # Filter out None values for averages
        valid_volumes = [v for v in volumes if v is not None and v > 0]
        avg_volume = sum(valid_volumes) / len(valid_volumes) if valid_volumes else 0

        latest_vol = volumes[-1] if volumes[-1] else 0
        latest_close = closes[-1] if closes[-1] else 0
        prev_close = closes[-2] if len(closes) > 1 and closes[-2] else latest_close

        vol_ratio = latest_vol / avg_volume if avg_volume > 0 else 1.0
        price_change_pct = ((latest_close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

        return {
            "ticker": ticker,
            "price": round(latest_close, 2),
            "price_change_pct": round(price_change_pct, 2),
            "volume": latest_vol,
            "avg_volume_30d": round(avg_volume, 0),
            "volume_ratio": round(vol_ratio, 2),
        }

    except Exception as e:
        logger.warning("Failed to fetch ETF data for %s: %s", ticker, e)
        return None


async def fetch_etf_flows():
    """Fetch BTC ETF volume and price data, compute flow sentiment proxy.

    Stores in Redis key `etf:flows` with:
    - etfs: list of per-ticker data
    - flow_score: -1 to +1 composite (positive = net buying, negative = net selling)
    - total_volume_ratio: weighted average volume ratio across all ETFs
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            etf_data = []
            for ticker in ETF_TICKERS:
                data = await _fetch_etf_data(client, ticker)
                if data:
                    etf_data.append(data)

        if not etf_data:
            logger.warning("No ETF data fetched")
            return

        # Compute flow score: volume-weighted price direction
        # High volume amplifies the signal, low volume dampens it
        total_weighted_score = 0.0
        total_volume = 0.0

        for etf in etf_data:
            vol = etf["volume"] or 0
            ratio = etf["volume_ratio"]
            pct = etf["price_change_pct"]

            # Volume amplifier: ratio > 1.5 = high conviction, < 0.5 = low conviction
            amplifier = min(ratio, 3.0)  # cap at 3x

            # Score: direction * amplifier, clamped to [-1, 1]
            if pct > 0:
                score = min(amplifier * (pct / 5.0), 1.0)  # 5% move at 1x vol = max
            elif pct < 0:
                score = max(-amplifier * (abs(pct) / 5.0), -1.0)
            else:
                score = 0.0

            total_weighted_score += score * vol
            total_volume += vol

        flow_score = total_weighted_score / total_volume if total_volume > 0 else 0.0
        flow_score = max(-1.0, min(1.0, flow_score))

        avg_vol_ratio = sum(e["volume_ratio"] for e in etf_data) / len(etf_data)

        result = {
            "etfs": etf_data,
            "flow_score": round(flow_score, 4),
            "total_volume_ratio": round(avg_vol_ratio, 2),
            "etf_count": len(etf_data),
        }

        r = await get_redis()
        await set_with_ts(r, "etf:flows", json.dumps(result))
        logger.info(
            "ETF flow proxy: score=%.4f, vol_ratio=%.2fx (%d ETFs)",
            flow_score, avg_vol_ratio, len(etf_data),
        )

    except Exception as e:
        logger.error("fetch_etf_flows failed: %s", e)
