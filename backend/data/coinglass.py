"""CoinGlass data fetcher — long/short ratio, OI, liquidations, funding rates."""

import json
import logging

import httpx

from config import settings
from redis_client import get_redis

logger = logging.getLogger(__name__)

COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"


async def fetch_coinglass():
    """Fetch long/short ratio, open interest, liquidation history, and funding
    rates from CoinGlass API. Store in Redis."""
    try:
        headers = {"coinglassSecret": settings.coinglass_api_key}
        result = {}

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            # Long/Short ratio
            try:
                resp = await client.get(
                    f"{COINGLASS_BASE}/long_short",
                    params={"symbol": "BTC", "interval": "h1"},
                )
                resp.raise_for_status()
                data = resp.json()
                ls_data = data.get("data", [])
                if ls_data:
                    latest = ls_data[-1] if isinstance(ls_data, list) else ls_data
                    result["long_short_ratio"] = {
                        "long_rate": latest.get("longRate", 0),
                        "short_rate": latest.get("shortRate", 0),
                        "long_short_ratio": latest.get("longShortRatio", 0),
                    }
            except Exception as e:
                logger.warning("CoinGlass long/short failed: %s", e)

            # Open Interest
            try:
                resp = await client.get(
                    f"{COINGLASS_BASE}/open_interest",
                    params={"symbol": "BTC", "interval": "0"},
                )
                resp.raise_for_status()
                data = resp.json()
                oi_data = data.get("data", {})
                result["open_interest"] = {
                    "total_oi": oi_data.get("openInterest", 0),
                    "oi_change_24h": oi_data.get("oiChange24h", 0),
                }
            except Exception as e:
                logger.warning("CoinGlass OI failed: %s", e)

            # Liquidation history
            try:
                resp = await client.get(
                    f"{COINGLASS_BASE}/liquidation_history",
                    params={"symbol": "BTC", "type": "h1"},
                )
                resp.raise_for_status()
                data = resp.json()
                liq_data = data.get("data", [])
                if liq_data:
                    latest = liq_data[-1] if isinstance(liq_data, list) else liq_data
                    result["liquidations"] = {
                        "long_liquidations": latest.get("longLiquidationUsd", 0),
                        "short_liquidations": latest.get("shortLiquidationUsd", 0),
                        "total_liquidations": latest.get("liquidationUsd", 0),
                    }
            except Exception as e:
                logger.warning("CoinGlass liquidations failed: %s", e)

            # Funding rates
            try:
                resp = await client.get(
                    f"{COINGLASS_BASE}/funding",
                    params={"symbol": "BTC"},
                )
                resp.raise_for_status()
                data = resp.json()
                funding_data = data.get("data", [])
                funding_rates = {}
                if isinstance(funding_data, list):
                    for entry in funding_data:
                        exchange = entry.get("exchangeName", "unknown")
                        funding_rates[exchange] = entry.get("rate", 0)
                result["funding_rates"] = funding_rates
            except Exception as e:
                logger.warning("CoinGlass funding failed: %s", e)

        r = await get_redis()
        await r.set("coinglass:data", json.dumps(result))
        logger.info("Stored CoinGlass data with %d sections", len(result))

    except Exception as e:
        logger.error("fetch_coinglass failed: %s", e)
