"""On-chain data fetchers — Glassnode metrics and stablecoin reserves."""

import json
import logging

import httpx

from config import settings
from redis_client import get_redis

logger = logging.getLogger(__name__)

GLASSNODE_BASE = "https://api.glassnode.com/v1/metrics"


async def _glassnode_get(client: httpx.AsyncClient, endpoint: str) -> float | None:
    """Helper to fetch a single Glassnode metric value."""
    try:
        resp = await client.get(
            f"{GLASSNODE_BASE}/{endpoint}",
            params={"a": "BTC", "api_key": settings.glassnode_api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return data[-1].get("v")
    except Exception as e:
        logger.warning("Glassnode %s failed: %s", endpoint, e)
    return None


async def fetch_onchain():
    """Fetch on-chain metrics from Glassnode: MVRV, SOPR, exchange flows,
    miner outflow, supply. Compute net_exchange_flow. Store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            mvrv = await _glassnode_get(client, "market/mvrv")
            sopr = await _glassnode_get(client, "indicators/sopr")
            exchange_inflow = await _glassnode_get(
                client, "transactions/transfers_volume_to_exchanges_sum"
            )
            exchange_outflow = await _glassnode_get(
                client, "transactions/transfers_volume_from_exchanges_sum"
            )
            miner_outflow = await _glassnode_get(
                client, "mining/miners_outflow_multiple"
            )
            supply_in_profit = await _glassnode_get(
                client, "supply/supply_in_profit"
            )

        net_exchange_flow = None
        if exchange_inflow is not None and exchange_outflow is not None:
            net_exchange_flow = exchange_inflow - exchange_outflow

        result = {
            "mvrv": mvrv,
            "sopr": sopr,
            "exchange_inflow": exchange_inflow,
            "exchange_outflow": exchange_outflow,
            "net_exchange_flow": net_exchange_flow,
            "miner_outflow": miner_outflow,
            "supply_in_profit": supply_in_profit,
        }

        r = await get_redis()
        await r.set("onchain:data", json.dumps(result))
        logger.info("Stored on-chain data: MVRV=%s, SOPR=%s", mvrv, sopr)

    except Exception as e:
        logger.error("fetch_onchain failed: %s", e)


async def fetch_stablecoin_reserves():
    """Fetch USDT market cap from CoinGecko as stablecoin reserve proxy.
    Store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/tether",
                params={"localization": "false", "tickers": "false",
                        "community_data": "false", "developer_data": "false"},
            )
            resp.raise_for_status()
            data = resp.json()

        market_data = data.get("market_data", {})
        market_cap = market_data.get("market_cap", {}).get("usd", 0)
        total_supply = market_data.get("total_supply", 0)

        result = {
            "usdt_market_cap": market_cap,
            "usdt_total_supply": total_supply,
        }

        r = await get_redis()
        await r.set("onchain:stablecoin", json.dumps(result))
        logger.info("Stored stablecoin reserves: USDT mcap=%s", market_cap)

    except Exception as e:
        logger.error("fetch_stablecoin_reserves failed: %s", e)
