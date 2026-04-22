"""Derivatives data fetcher — Hyperliquid REST API replaces CoinGlass.

Hyperliquid endpoint used:
  POST https://api.hyperliquid.xyz/info
  Body: {"type": "metaAndAssetCtxs"}

The response is a two-element list:
  [0] universe metadata (list of asset dicts with "name", etc.)
  [1] asset contexts (list of dicts with openInterest, funding, etc.)

BTC is matched by asset name == "BTC".

Long/short ratio is approximated from the funding rate:
  - Positive funding  → longs pay shorts → long-heavy market → ratio > 1
  - Negative funding  → shorts pay longs → short-heavy market → ratio < 1
  - Magnitude capped to a ±5× multiplier so extreme rates don't produce
    nonsensical ratio values.

Redis key ``coinglass:data`` structure (unchanged from original):
  funding_rates:    {"rate": float}          — 8-h funding rate as a decimal
  long_short_ratio: {"ratio": float,
                     "long_rate": float,
                     "short_rate": float}
  open_interest:    {"total_oi": float,      — OI in USD
                     "oi_change_24h": float} — % change (null — not provided)
  liquidations:     null                     — not available from free source
"""

import json
import logging

import httpx

from redis_client import get_redis

logger = logging.getLogger(__name__)

HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"
_BTC_ASSET_NAME = "BTC"


def _ls_ratio_from_funding(funding_rate: float) -> dict:
    """Approximate long/short ratio and split from a funding rate.

    Args:
        funding_rate: 8-h funding rate as a decimal (e.g. 0.0001).

    Returns:
        Dict with keys ``ratio``, ``long_rate``, ``short_rate``.
    """
    # Scale: 0.0001 funding ≈ neutral (1.0 ratio). Each 0.0001 shifts by 0.5.
    # Clamp multiplier to [-5, +5] range to avoid absurd outputs.
    multiplier = funding_rate / 0.0001
    multiplier = max(-5.0, min(5.0, multiplier))

    ratio = round(1.0 + multiplier * 0.1, 4)
    ratio = max(0.1, ratio)  # can't be negative or zero

    # Derive rough split percentages
    long_rate = round(ratio / (1.0 + ratio), 4)
    short_rate = round(1.0 - long_rate, 4)

    return {"ratio": ratio, "long_rate": long_rate, "short_rate": short_rate}


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

    Writes ``coinglass:data`` with the same structure the engine expects:
    - funding_rates.rate
    - long_short_ratio.ratio / long_rate / short_rate
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
                result["long_short_ratio"] = _ls_ratio_from_funding(funding_rate)
                logger.info(
                    "Hyperliquid BTC funding=%.6f, approx L/S ratio=%.4f",
                    funding_rate,
                    result["long_short_ratio"]["ratio"],
                )

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
        await r.set("coinglass:data", json.dumps(result))
        logger.info("Stored derivatives data with %d sections", len(result))

    except Exception as exc:
        logger.error("fetch_coinglass failed: %s", exc)
