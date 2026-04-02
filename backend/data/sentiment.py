"""Sentiment data fetchers — Fear & Greed, BTC Dominance, Polymarket."""

import json
import logging

import httpx

from redis_client import get_redis

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
            resp = await client.get("https://api.coingecko.com/api/v3/global")
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
    """Fetch crypto-related markets from Polymarket Gamma API, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={"tag": "crypto", "limit": 20, "active": True},
            )
            resp.raise_for_status()
            data = resp.json()

        markets = []
        for m in data if isinstance(data, list) else data.get("data", []):
            markets.append(
                {
                    "question": m.get("question", ""),
                    "slug": m.get("slug", ""),
                    "volume": m.get("volume", 0),
                    "liquidity": m.get("liquidity", 0),
                    "outcomes": m.get("outcomes", []),
                    "outcome_prices": m.get("outcomePrices", []),
                    "end_date": m.get("endDate", ""),
                }
            )

        r = await get_redis()
        await r.set("sentiment:polymarket", json.dumps(markets))
        logger.info("Stored %d Polymarket markets", len(markets))

    except Exception as e:
        logger.error("fetch_polymarket failed: %s", e)
