"""Derivatives data fetcher — Hyperliquid REST API replaces CoinGlass.

Hyperliquid endpoint used:
  POST https://api.hyperliquid.xyz/info
  Body: {"type": "metaAndAssetCtxs"}

The response is a two-element list:
  [0] universe metadata (list of asset dicts with "name", etc.)
  [1] asset contexts (list of dicts with openInterest, funding, etc.)

BTC is matched by asset name == "BTC".

Redis key ``coinglass:data`` structure:
  funding_rates:    {"rate": float}          — 8-h funding rate as a decimal
  open_interest:    {"total_oi": float,      — OI in USD
                     "oi_change_24h": float} — % change (null — not provided)
  liquidations:     null                     — not available from free source

Note: a long/short ratio synthesised from the funding rate was removed
because it is mathematically the same signal as the funding rate itself
(just with a linear transform and a rename), which caused the engine to
double-count funding. The real measured long/short ratio comes from
Coinalyze; see data/coinalyze.py.
"""

import json
import logging

import httpx

from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"
_BTC_ASSET_NAME = "BTC"


async def _fetch_hyperliquid_btc(client: httpx.AsyncClient) -> dict | None:
    """Query Hyperliquid metaAndAssetCtxs and return the BTC asset context.

    Returns:
        Dict with keys from Hyperliquid (funding, openInterest, etc.) or None
        on any error.
    """
    try:
        resp = await client.post(
            HYPERLIQUID_INFO,
            json={"type": "metaAndAssetCtxs"},
        )
        resp.raise_for_status()
        payload = resp.json()

        if not isinstance(payload, list) or len(payload) < 2:
            logger.warning("Hyperliquid unexpected response shape")
            return None

        universe: list[dict] = payload[0].get("universe", [])
        asset_ctxs: list[dict] = payload[1]

        for idx, asset in enumerate(universe):
            if asset.get("name") == _BTC_ASSET_NAME:
                if idx < len(asset_ctxs):
                    return asset_ctxs[idx]
                break

        logger.warning("BTC not found in Hyperliquid universe response")
        return None

    except Exception as exc:
        logger.warning("Hyperliquid fetch failed: %s", exc)
        return None


async def fetch_coinglass() -> None:
    """Fetch derivatives metrics from Hyperliquid and store in Redis.

    Writes ``coinglass:data`` with:
    - funding_rates.rate
    - open_interest.total_oi / oi_change_24h
    - liquidations (null — not available without a paid source)
    """
    try:
        result: dict = {}

        async with httpx.AsyncClient(timeout=20) as client:
            btc_ctx = await _fetch_hyperliquid_btc(client)

        if btc_ctx is not None:
            # --- Funding rate ---
            raw_funding = btc_ctx.get("funding")
            funding_rate: float | None = None
            if raw_funding is not None:
                try:
                    funding_rate = float(raw_funding)
                except (TypeError, ValueError):
                    pass

            if funding_rate is not None:
                result["funding_rates"] = {"rate": funding_rate}
                logger.info("Hyperliquid BTC funding=%.6f", funding_rate)

            # --- Open Interest ---
            raw_oi = btc_ctx.get("openInterest")
            if raw_oi is not None:
                try:
                    oi_usd = float(raw_oi)
                    result["open_interest"] = {
                        "total_oi": oi_usd,
                        # 24-h change not provided by this endpoint
                        "oi_change_24h": None,
                    }
                    logger.info("Hyperliquid BTC OI=%.2f USD", oi_usd)
                except (TypeError, ValueError):
                    pass
        else:
            logger.warning("No BTC context from Hyperliquid — derivatives data unavailable")

        # Liquidations: not available from any free source; keep key absent
        # so the engine skips it gracefully.

        r = await get_redis()
        await set_with_ts(r, "coinglass:data", json.dumps(result))
        logger.info("Stored derivatives data with %d sections", len(result))

    except Exception as exc:
        logger.error("fetch_coinglass failed: %s", exc)
