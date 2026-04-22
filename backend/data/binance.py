"""Binance Futures public API fetchers — funding rates and open interest.

No API key required. Uses Binance USDM futures public endpoints.

Endpoints used:
  /fapi/v1/fundingRate   — historical funding rates (no auth)
  /fapi/v1/openInterest  — current open interest snapshot (no auth)

Redis keys written:
  binance:funding       — latest and avg-3 funding rate for BTCUSDT perp
  binance:open_interest — current OI with % change vs previous reading
"""

import json
import logging
import time

import httpx

from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

_BASE = "https://fapi.binance.com"
_FUNDING_URL = f"{_BASE}/fapi/v1/fundingRate"
_OI_URL = f"{_BASE}/fapi/v1/openInterest"
_SYMBOL = "BTCUSDT"


async def fetch_binance_funding() -> None:
    """Fetch BTCUSDT perpetual funding rate from Binance and store in Redis.

    Requests the last 3 funding rate records to compute a smoothed average
    alongside the single latest rate.

    Redis key ``binance:funding`` structure:
      rate       float  — latest 8-h funding rate
      avg_rate   float  — simple average of the 3 most recent funding rates
      timestamp  int    — Unix timestamp (seconds) of the latest record
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _FUNDING_URL,
                params={"symbol": _SYMBOL, "limit": 3},
            )
            resp.raise_for_status()
            data: list[dict] = resp.json()

        if not data or not isinstance(data, list):
            logger.warning("fetch_binance_funding: unexpected response shape")
            return

        # Latest entry is the last element in the list
        latest = data[-1]
        rate = float(latest.get("fundingRate", 0) or 0)
        # fundingTime is in milliseconds — convert to seconds
        raw_ts = latest.get("fundingTime", 0)
        timestamp = int(raw_ts) // 1000 if raw_ts else int(time.time())

        # Average over last 3 rates for smoothing
        rates = [float(entry.get("fundingRate", 0) or 0) for entry in data]
        avg_rate = round(sum(rates) / len(rates), 8) if rates else rate

        result = {
            "rate": round(rate, 8),
            "avg_rate": avg_rate,
            "timestamp": timestamp,
        }

        r = await get_redis()
        await set_with_ts(r, "binance:funding", json.dumps(result))
        logger.info(
            "Stored Binance funding: rate=%.6f, avg_rate=%.6f",
            rate,
            avg_rate,
        )

    except Exception as exc:
        logger.warning("fetch_binance_funding failed: %s", exc)


async def fetch_binance_oi() -> None:
    """Fetch BTCUSDT perpetual open interest from Binance and store in Redis.

    Reads the previous OI from Redis to compute a percentage change before
    overwriting with the fresh reading.

    Redis key ``binance:open_interest`` structure:
      oi              float        — current open interest in BTC
      oi_change_pct   float|null   — % change vs previous stored reading
      timestamp       int          — Unix timestamp (seconds) from the exchange
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _OI_URL,
                params={"symbol": _SYMBOL},
            )
            resp.raise_for_status()
            data: dict = resp.json()

        oi = float(data.get("openInterest", 0) or 0)
        raw_ts = data.get("time", 0)
        timestamp = int(raw_ts) // 1000 if raw_ts else int(time.time())

        r = await get_redis()

        # Compute change vs previous stored reading
        oi_change_pct: float | None = None
        prev_raw = await r.get("binance:open_interest")
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
                prev_oi = float(prev.get("oi") or 0)
                if prev_oi > 0:
                    oi_change_pct = round(((oi - prev_oi) / prev_oi) * 100, 4)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass

        result = {
            "oi": round(oi, 4),
            "oi_change_pct": oi_change_pct,
            "timestamp": timestamp,
        }

        await set_with_ts(r, "binance:open_interest", json.dumps(result))
        logger.info(
            "Stored Binance OI: %.4f BTC, change=%s%%",
            oi,
            f"{oi_change_pct:.4f}" if oi_change_pct is not None else "N/A",
        )

    except Exception as exc:
        logger.warning("fetch_binance_oi failed: %s", exc)
