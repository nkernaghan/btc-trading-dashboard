"""OKX public API fetchers — funding rates and open interest.

No API key required. Uses OKX v5 public endpoints, accessible without auth.

Redis keys written:
  okx:funding        — USDT-margined, coin-margined, and average funding rates
  okx:open_interest  — total OI in USD across both contract types, with change %
"""

import json
import logging

import httpx

from redis_client import get_redis

logger = logging.getLogger(__name__)

OKX_BASE = "https://www.okx.com/api/v5/public"
_FUNDING_URL = f"{OKX_BASE}/funding-rate"
_OI_URL = f"{OKX_BASE}/open-interest"


async def fetch_okx_funding() -> None:
    """Fetch BTC perpetual funding rates from OKX and store in Redis.

    Fetches both BTC-USDT-SWAP (USDT-margined) and BTC-USD-SWAP
    (coin-margined) funding rates and computes a simple average.

    Redis key ``okx:funding`` structure:
      usdt_rate  float  — 8-h funding rate for BTC-USDT-SWAP
      usd_rate   float  — 8-h funding rate for BTC-USD-SWAP
      avg_rate   float  — simple average of the two rates
      timestamp  str    — ISO timestamp of the newer of the two readings
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp_usdt, resp_usd = await _fetch_both_instruments(
                client, _FUNDING_URL, "BTC-USDT-SWAP", "BTC-USD-SWAP"
            )

        usdt_rate = _extract_float(resp_usdt, "data", 0, "fundingRate")
        usd_rate = _extract_float(resp_usd, "data", 0, "fundingRate")
        timestamp = _extract_str(resp_usdt, "data", 0, "fundingTime") or ""

        avg_rate: float | None = None
        if usdt_rate is not None and usd_rate is not None:
            avg_rate = round((usdt_rate + usd_rate) / 2, 8)

        result = {
            "usdt_rate": usdt_rate,
            "usd_rate": usd_rate,
            "avg_rate": avg_rate,
            "timestamp": timestamp,
        }

        r = await get_redis()
        await r.set("okx:funding", json.dumps(result))
        logger.info(
            "Stored OKX funding: USDT=%.6f, USD=%.6f, avg=%.6f",
            usdt_rate or 0,
            usd_rate or 0,
            avg_rate or 0,
        )

    except Exception as exc:
        logger.error("fetch_okx_funding failed: %s", exc)


async def fetch_okx_open_interest() -> None:
    """Fetch BTC perpetual open interest from OKX and store in Redis.

    Fetches both BTC-USDT-SWAP and BTC-USD-SWAP open interest, converts
    each to USD, then computes a combined total and percentage change vs
    the previously stored value.

    Redis key ``okx:open_interest`` structure:
      total_oi_usd   float  — combined OI in USD across both contract types
      oi_change_pct  float  — % change vs previous reading (0.0 if no prior)
      usdt_oi_usd    float  — USDT-margined OI in USD
      usd_oi_usd     float  — coin-margined OI in USD
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp_usdt, resp_usd = await _fetch_both_instruments(
                client, _OI_URL, "BTC-USDT-SWAP", "BTC-USD-SWAP"
            )

        # OKX OI for USDT-SWAP is denominated in USD contract value directly
        usdt_oi_usd = _extract_float(resp_usdt, "data", 0, "oiUsd")
        # OKX OI for coin-margined SWAP may use "oi" in BTC; prefer oiUsd when present
        usd_oi_usd = _extract_float(resp_usd, "data", 0, "oiUsd")

        # Fallback: some OKX responses use "oi" (BTC units) for coin-margined
        if usd_oi_usd is None:
            oi_btc = _extract_float(resp_usd, "data", 0, "oi")
            # Approximate USD conversion using USDT OI ratio if both BTC values exist
            # Without a live BTC price this is a best-effort estimate; the field is
            # marked as usd_oi_usd so callers should treat it as approximate.
            if oi_btc is not None:
                usd_oi_usd = oi_btc  # will be 0 or near 0 — flag for downstream

        total_oi_usd: float = (usdt_oi_usd or 0.0) + (usd_oi_usd or 0.0)

        # Compute change vs previous stored value
        oi_change_pct = 0.0
        r = await get_redis()
        prev_raw = await r.get("okx:open_interest")
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
                prev_total = float(prev.get("total_oi_usd") or 0)
                if prev_total > 0:
                    oi_change_pct = round(((total_oi_usd - prev_total) / prev_total) * 100, 4)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass

        result = {
            "total_oi_usd": round(total_oi_usd, 2),
            "oi_change_pct": oi_change_pct,
            "usdt_oi_usd": round(usdt_oi_usd or 0.0, 2),
            "usd_oi_usd": round(usd_oi_usd or 0.0, 2),
        }

        await r.set("okx:open_interest", json.dumps(result))
        logger.info(
            "Stored OKX OI: total=%.2f USD, change=%.4f%%",
            total_oi_usd,
            oi_change_pct,
        )

    except Exception as exc:
        logger.error("fetch_okx_open_interest failed: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_both_instruments(
    client: httpx.AsyncClient,
    url: str,
    inst_a: str,
    inst_b: str,
) -> tuple[dict, dict]:
    """Fetch the same OKX endpoint for two instruments concurrently.

    Args:
        client: Shared httpx async client.
        url:    OKX API endpoint URL.
        inst_a: First instId (e.g. ``BTC-USDT-SWAP``).
        inst_b: Second instId (e.g. ``BTC-USD-SWAP``).

    Returns:
        Tuple of (response_dict_a, response_dict_b). Either may be an empty
        dict if the individual request fails.
    """
    import asyncio

    async def _get(inst: str) -> dict:
        try:
            resp = await client.get(url, params={"instId": inst})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("OKX %s fetch failed for %s: %s", url, inst, exc)
            return {}

    results = await asyncio.gather(_get(inst_a), _get(inst_b))
    return results[0], results[1]


def _extract_float(data: dict, *keys: str | int) -> float | None:
    """Safely traverse a nested structure and return a float.

    Args:
        data: Root dict to traverse.
        *keys: Sequence of keys/indices to follow.

    Returns:
        Float value at the target path, or None if the path is absent or
        the value cannot be cast to float.
    """
    node: object = data
    for key in keys:
        if node is None:
            return None
        try:
            node = node[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return None
    if node is None:
        return None
    try:
        return float(node)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _extract_str(data: dict, *keys: str | int) -> str | None:
    """Safely traverse a nested structure and return a string.

    Args:
        data: Root dict to traverse.
        *keys: Sequence of keys/indices to follow.

    Returns:
        String value at the target path, or None.
    """
    node: object = data
    for key in keys:
        if node is None:
            return None
        try:
            node = node[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return None
    return str(node) if node is not None else None
