"""On-chain data fetchers — free API replacements for Glassnode.

Sources used:
- CoinGecko /coins/bitcoin  — market_cap, total_volume, market_cap_change_24h
- Blockchain.com /stats     — trade_volume_btc, hash_rate, miners_revenue_btc
- Mempool.space             — hashrate (backup, not stored but logged)

MVRV approximation: CoinGecko `market_cap_to_tvl_ratio` when available;
falls back to market_cap / (circulating_supply * 200-day_price_avg) which
is a rough realised-cap proxy. When neither is calculable the field is null.

Exchange flow proxy: Blockchain.com `trade_volume_btc` (24-h exchange volume)
is used as a single combined volume figure.  True inflow/outflow split is not
available from free sources, so both fields are set to half of total volume
and net_exchange_flow is set to 0 (neutral — the engine skips null/zero safely).
"""

import json
import logging

import httpx

from redis_client import get_redis

logger = logging.getLogger(__name__)

COINGECKO_BTC = "https://api.coingecko.com/api/v3/coins/bitcoin"
BLOCKCHAIN_STATS = "https://api.blockchain.info/stats"
COINGECKO_TETHER = "https://api.coingecko.com/api/v3/coins/tether"


async def _fetch_coingecko_btc(client: httpx.AsyncClient) -> dict:
    """Fetch Bitcoin market data from CoinGecko (no key required)."""
    try:
        resp = await client.get(
            COINGECKO_BTC,
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
            },
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("CoinGecko BTC fetch failed: %s", exc)
        return {}


async def _fetch_blockchain_stats(client: httpx.AsyncClient) -> dict:
    """Fetch network stats from Blockchain.com (no key required)."""
    try:
        resp = await client.get(BLOCKCHAIN_STATS)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Blockchain.com stats fetch failed: %s", exc)
        return {}


def _approx_mvrv(cg_data: dict) -> float | None:
    """Derive a MVRV approximation from CoinGecko data.

    Priority order:
    1. market_cap_to_tvl_ratio if CoinGecko provides it directly.
    2. market_cap / (circulating_supply * ath_price * 0.5) as a very rough
       realised-cap proxy — directionally correct but not numerically precise.
    Returns None if insufficient data.
    """
    market_data = cg_data.get("market_data", {})
    if not market_data:
        return None

    # CoinGecko sometimes surfaces this directly
    tvl_ratio = market_data.get("market_cap_to_tvl_ratio")
    if tvl_ratio is not None:
        try:
            return float(tvl_ratio)
        except (TypeError, ValueError):
            pass

    # Fallback: market_cap / rough_realised_cap
    market_cap = market_data.get("market_cap", {}).get("usd")
    circ_supply = market_data.get("circulating_supply")
    ath_price = market_data.get("ath", {}).get("usd")

    if market_cap and circ_supply and ath_price and ath_price > 0:
        # Realised cap proxy: assume average held cost = 50% of ATH
        realised_cap_proxy = circ_supply * ath_price * 0.5
        if realised_cap_proxy > 0:
            return round(market_cap / realised_cap_proxy, 4)

    return None


async def fetch_onchain() -> None:
    """Fetch on-chain proxy metrics from free APIs and store in Redis.

    Fields written to ``onchain:data``:
    - mvrv              float | None  — approximated from CoinGecko
    - sopr              None          — no free real-time source
    - exchange_inflow   float | None  — half of Blockchain.com daily trade volume (BTC)
    - exchange_outflow  float | None  — half of Blockchain.com daily trade volume (BTC)
    - net_exchange_flow float | None  — 0 when split is unavailable; null on error
    - miner_outflow     float | None  — miners_revenue_btc from Blockchain.com (proxy)
    - supply_in_profit  None          — no free real-time source
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            cg_data, bc_stats = await _fetch_coingecko_btc(client), None
            bc_stats = await _fetch_blockchain_stats(client)

        mvrv = _approx_mvrv(cg_data)

        # Exchange flow proxy via Blockchain.com total trade volume
        trade_volume_btc: float | None = None
        exchange_inflow: float | None = None
        exchange_outflow: float | None = None
        net_exchange_flow: float | None = None
        miner_outflow: float | None = None

        if bc_stats:
            raw_vol = bc_stats.get("trade_volume_btc")
            if raw_vol is not None:
                try:
                    trade_volume_btc = float(raw_vol)
                    # Split evenly — true directional split requires a paid source
                    exchange_inflow = round(trade_volume_btc / 2, 4)
                    exchange_outflow = round(trade_volume_btc / 2, 4)
                    net_exchange_flow = 0.0
                except (TypeError, ValueError):
                    pass

            raw_miners = bc_stats.get("miners_revenue_btc")
            if raw_miners is not None:
                try:
                    miner_outflow = float(raw_miners)
                except (TypeError, ValueError):
                    pass

        result = {
            "mvrv": mvrv,
            "sopr": None,
            "exchange_inflow": exchange_inflow,
            "exchange_outflow": exchange_outflow,
            "net_exchange_flow": net_exchange_flow,
            "miner_outflow": miner_outflow,
            "supply_in_profit": None,
        }

        r = await get_redis()
        await r.set("onchain:data", json.dumps(result))
        logger.info(
            "Stored on-chain data (free sources): MVRV=%.4g, trade_vol_btc=%s, miner_rev_btc=%s",
            mvrv or 0,
            trade_volume_btc,
            miner_outflow,
        )

    except Exception as exc:
        logger.error("fetch_onchain failed: %s", exc)


async def fetch_stablecoin_reserves() -> None:
    """Fetch USDT market cap from CoinGecko as stablecoin reserve proxy.
    Store in Redis under ``onchain:stablecoin``."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                COINGECKO_TETHER,
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "false",
                },
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

    except Exception as exc:
        logger.error("fetch_stablecoin_reserves failed: %s", exc)
