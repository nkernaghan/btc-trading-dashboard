"""On-chain data fetchers — free API replacements for Glassnode.

Sources used:
- CoinGecko /coins/markets  — BTC + USDT market data in a single call
- Blockchain.com /stats      — trade_volume_btc, hash_rate, miners_revenue_btc

The field stored under the `mvrv` key is NOT real MVRV. It's an
ATH-proximity proxy (2 * price/ATH) because free APIs do not expose
realised cap. See `_approx_mvrv` for the math and engine.py for the
voting bands that match the proxy's actual range.

Exchange flow proxy: Blockchain.com `trade_volume_btc` is total exchange volume.
True inflow/outflow split requires a paid source, so net_exchange_flow is 0.
"""

import json
import logging

import httpx

from config import settings
from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
BLOCKCHAIN_STATS = "https://api.blockchain.info/stats"


def _cg_headers() -> dict:
    """Return CoinGecko headers with API key if configured."""
    if settings.coingecko_api_key:
        return {"x-cg-demo-api-key": settings.coingecko_api_key}
    return {}


async def _fetch_coingecko_markets(client: httpx.AsyncClient) -> list[dict]:
    """Fetch BTC + USDT market data from CoinGecko in a single call."""
    try:
        resp = await client.get(
            COINGECKO_MARKETS,
            params={
                "vs_currency": "usd",
                "ids": "bitcoin,tether",
                "order": "market_cap_desc",
                "sparkline": "false",
                "price_change_percentage": "24h,7d",
            },
            headers=_cg_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("CoinGecko markets fetch failed: %s", exc)
        return []


async def _fetch_blockchain_stats(client: httpx.AsyncClient) -> dict:
    """Fetch network stats from Blockchain.com (no key required)."""
    try:
        resp = await client.get(BLOCKCHAIN_STATS)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Blockchain.com stats fetch failed: %s", exc)
        return {}


def _find_coin(markets: list[dict], coin_id: str) -> dict | None:
    """Find a coin by id in the markets response."""
    for m in markets:
        if m.get("id") == coin_id:
            return m
    return None


def _approx_mvrv(btc: dict) -> float | None:
    """Return an ATH-proximity proxy that is stored under the key `mvrv`.

    Formula: market_cap / (circulating_supply * ath * 0.5). This
    algebraically simplifies to 2 * (current_price / ATH) — i.e. it
    measures how close the current price is to the all-time high, not
    true MVRV (market value / realised value). Real MVRV requires
    realised-cap data from a paid on-chain source.

    The engine's voting bands for this field are calibrated to the
    proxy's actual range (0.0 to ~2.0), not to canonical MVRV
    thresholds. If this is ever replaced with real MVRV, revert the
    bands there to bull:(0.5, 2.0), bear:(3.5, 10).

    Typical proxy values:
      ~0.2  -> price ~10% of ATH (deep discount / capitulation)
      ~1.0  -> price ~50% of ATH (mid-cycle)
      ~1.6  -> price ~80% of ATH (approaching top)
      ~2.0  -> price at ATH
    """
    market_cap = btc.get("market_cap")
    circ_supply = btc.get("circulating_supply")
    ath = btc.get("ath")

    if market_cap and circ_supply and ath and ath > 0:
        realised_cap_proxy = circ_supply * ath * 0.5
        if realised_cap_proxy > 0:
            return round(market_cap / realised_cap_proxy, 4)
    return None


async def fetch_onchain() -> None:
    """Fetch on-chain proxy metrics from free APIs and store in Redis.

    Makes ONE CoinGecko call for both BTC and USDT data, plus one Blockchain.com call.
    Stores results in three Redis keys: onchain:data, onchain:stablecoin, etf:flows.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            markets = await _fetch_coingecko_markets(client)
            bc_stats = await _fetch_blockchain_stats(client)

        btc = _find_coin(markets, "bitcoin") or {}
        usdt = _find_coin(markets, "tether") or {}

        # ---- BTC on-chain data ----
        mvrv = _approx_mvrv(btc) if btc else None

        trade_volume_btc: float | None = None
        miner_outflow: float | None = None

        if bc_stats:
            raw_vol = bc_stats.get("trade_volume_btc")
            if raw_vol is not None:
                try:
                    trade_volume_btc = float(raw_vol)
                except (TypeError, ValueError):
                    pass

            raw_miners = bc_stats.get("miners_revenue_btc")
            if raw_miners is not None:
                try:
                    miner_outflow = float(raw_miners)
                except (TypeError, ValueError):
                    pass

        onchain_result = {
            "mvrv": mvrv,
            "sopr": None,
            "exchange_inflow": None,
            "exchange_outflow": None,
            "net_exchange_flow": None,
            "miner_outflow": miner_outflow,
            "supply_in_profit": None,
        }

        r = await get_redis()
        await set_with_ts(r, "onchain:data", json.dumps(onchain_result))

        # ---- USDT stablecoin data ----
        usdt_mcap = usdt.get("market_cap", 0) or 0
        usdt_supply = usdt.get("total_supply", 0) or 0

        prev_raw = await r.get("onchain:stablecoin")
        mcap_change_pct = 0.0
        if prev_raw:
            prev = json.loads(prev_raw)
            prev_mcap = prev.get("usdt_market_cap", 0)
            if prev_mcap and prev_mcap > 0:
                mcap_change_pct = ((usdt_mcap - prev_mcap) / prev_mcap) * 100.0

        stablecoin_result = {
            "usdt_market_cap": usdt_mcap,
            "usdt_total_supply": usdt_supply,
            "usdt_mcap_change_pct": round(mcap_change_pct, 4),
        }
        await set_with_ts(r, "onchain:stablecoin", json.dumps(stablecoin_result))

        # ---- ETF proxy data (from BTC market data) ----
        etf_result = {
            "last_updated": None,
            "flows": [],
            "btc_market_cap": btc.get("market_cap", 0),
            "btc_total_volume": btc.get("total_volume", 0),
            "btc_price_change_24h": btc.get("price_change_percentage_24h", 0),
        }
        await set_with_ts(r, "etf:flows", json.dumps(etf_result))

        logger.info(
            "Stored CoinGecko data (1 call): MVRV=%.4g, USDT_mcap=%.2fB, BTC_vol=%.2fB, miner_btc=%s",
            mvrv or 0,
            usdt_mcap / 1e9,
            btc.get("total_volume", 0) / 1e9,
            miner_outflow,
        )

    except Exception as exc:
        logger.error("fetch_onchain failed: %s", exc)
