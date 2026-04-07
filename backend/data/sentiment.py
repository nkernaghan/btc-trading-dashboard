"""Sentiment data fetchers — Fear & Greed, BTC Dominance, Polymarket."""

import json
import logging

import httpx

from config import settings
from redis_client import get_redis


def _cg_headers() -> dict:
    """Return CoinGecko headers with API key if configured."""
    if settings.coingecko_api_key:
        return {"x-cg-demo-api-key": settings.coingecko_api_key}
    return {}

logger = logging.getLogger(__name__)


async def fetch_fear_greed():
    """Fetch Crypto Fear & Greed Index, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            resp.raise_for_status()
            data = resp.json()

        fng = data.get("data", [{}])[0]
        result = {
            "value": int(fng.get("value", 0)),
            "classification": fng.get("value_classification", "Unknown"),
            "timestamp": int(fng.get("timestamp", 0)),
        }

        r = await get_redis()
        await r.set("sentiment:fear_greed", json.dumps(result))
        logger.info("Stored Fear & Greed: %s (%s)", result["value"], result["classification"])

    except Exception as e:
        logger.error("fetch_fear_greed failed: %s", e)


async def fetch_btc_dominance():
    """Fetch BTC dominance from CoinGecko global API, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/global", headers=_cg_headers())
            resp.raise_for_status()
            data = resp.json()

        market_data = data.get("data", {})
        btc_dom = market_data.get("market_cap_percentage", {}).get("btc", 0.0)
        total_mcap = market_data.get("total_market_cap", {}).get("usd", 0.0)

        result = {
            "btc_dominance": round(btc_dom, 2),
            "total_market_cap_usd": total_mcap,
        }

        r = await get_redis()
        await r.set("sentiment:btc_dominance", json.dumps(result))
        logger.info("Stored BTC dominance: %.2f%%", btc_dom)

    except Exception as e:
        logger.error("fetch_btc_dominance failed: %s", e)


async def fetch_polymarket():
    """Fetch crypto-related markets from Polymarket CLOB API, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use the CLOB API which doesn't require auth
            resp = await client.get(
                "https://clob.polymarket.com/markets",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Filter for crypto/BTC-related markets
        btc_keywords = ["bitcoin", "btc", "crypto", "ethereum", "eth"]
        markets = []
        raw_list = data if isinstance(data, list) else data.get("data", data.get("markets", []))
        for m in raw_list:
            question = (m.get("question", "") or "").lower()
            if any(kw in question for kw in btc_keywords):
                # Extract probability from tokens if available
                tokens = m.get("tokens", [])
                yes_price = None
                if tokens and isinstance(tokens, list):
                    for t in tokens:
                        if t.get("outcome", "").lower() == "yes":
                            yes_price = float(t.get("price", 0))
                            break

                markets.append({
                    "question": m.get("question", ""),
                    "yes_price": yes_price,
                    "volume": float(m.get("volume", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                    "active": m.get("active", True),
                })

        r = await get_redis()
        await r.set("sentiment:polymarket", json.dumps(markets))
        logger.info("Stored %d Polymarket crypto markets", len(markets))

    except Exception as e:
        logger.error("fetch_polymarket failed: %s", e)
