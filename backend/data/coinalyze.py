"""Coinalyze API fetcher — aggregated multi-exchange derivatives data.

Requires API key (free registration at coinalyze.net).
Rate limit: 40 requests/minute.

Endpoints used:
  /v1/liquidation-history  — BTC liquidation data across exchanges
  /v1/open-interest        — aggregated open interest
  /v1/funding-rate         — aggregated funding rates
  /v1/long-short-ratio     — global long/short account ratio

Redis keys written:
  coinalyze:liquidations  — recent liquidation totals (long/short)
  coinalyze:oi            — aggregated OI with change %
  coinalyze:funding       — aggregated funding rate across exchanges
  coinalyze:long_short    — global long/short ratio
"""

import json
import logging
import time

import httpx

from config import settings
from redis_client import get_redis

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coinalyze.net/v1"
# Binance BTCUSDT perp — highest volume venue, good proxy for aggregate
SYMBOL = "BTCUSDT_PERP.A"


def _headers() -> dict:
    return {"api_key": settings.coinalyze_api_key}


async def _get(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict | list | None:
    """Make an authenticated GET to Coinalyze. Returns parsed JSON or None."""
    try:
        resp = await client.get(
            f"{BASE_URL}{path}",
            params=params or {},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Coinalyze %s failed: %s", path, exc)
        return None


async def fetch_coinalyze_liquidations() -> None:
    """Fetch recent BTC liquidation data and store in Redis.

    Redis key ``coinalyze:liquidations`` structure:
      long_liquidations_usd   float  — total long liquidations in USD (last period)
      short_liquidations_usd  float  — total short liquidations in USD (last period)
      total_liquidations_usd  float  — combined total
      net_liquidations_usd    float  — long - short (positive = more longs liquidated = bearish)
      dominant_side            str    — "long" or "short" (which side got liquidated more)
    """
    try:
        now = int(time.time())
        # Last 4 hours of liquidation data
        since = now - 4 * 3600

        async with httpx.AsyncClient(timeout=20) as client:
            data = await _get(client, "/liquidation-history", {
                "symbols": SYMBOL,
                "interval": "1hour",
                "from": since,
                "to": now,
            })

        if not data or not isinstance(data, list) or len(data) == 0:
            return

        # Coinalyze returns array of candle objects with liquidation volumes
        total_long = 0.0
        total_short = 0.0

        for entry in data:
            # Fields: t (timestamp), l (long liq volume), s (short liq volume)
            if isinstance(entry, dict):
                total_long += float(entry.get("l", 0) or 0)
                total_short += float(entry.get("s", 0) or 0)

        total = total_long + total_short
        net = total_long - total_short

        result = {
            "long_liquidations_usd": round(total_long, 2),
            "short_liquidations_usd": round(total_short, 2),
            "total_liquidations_usd": round(total, 2),
            "net_liquidations_usd": round(net, 2),
            "dominant_side": "long" if total_long > total_short else "short",
        }

        r = await get_redis()
        await r.set("coinalyze:liquidations", json.dumps(result))
        logger.info(
            "Stored liquidations: long=%.0f, short=%.0f, net=%.0f",
            total_long, total_short, net,
        )

    except Exception as exc:
        logger.error("fetch_coinalyze_liquidations failed: %s", exc)


async def fetch_coinalyze_oi() -> None:
    """Fetch aggregated BTC open interest from Coinalyze.

    Redis key ``coinalyze:oi`` structure:
      open_interest      float  — latest OI value
      oi_change_pct      float  — % change vs previous stored value
    """
    try:
        now = int(time.time())
        since = now - 2 * 3600  # last 2 hours

        async with httpx.AsyncClient(timeout=20) as client:
            data = await _get(client, "/open-interest-history", {
                "symbols": SYMBOL,
                "interval": "1hour",
                "from": since,
                "to": now,
            })

        if not data or not isinstance(data, list) or len(data) == 0:
            return

        # Last entry is most recent
        latest = data[-1] if isinstance(data[-1], dict) else {}
        oi_value = float(latest.get("o", 0) or 0)  # 'o' = open interest

        r = await get_redis()

        # Compute change vs previous
        oi_change_pct = 0.0
        prev_raw = await r.get("coinalyze:oi")
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
                prev_oi = float(prev.get("open_interest", 0))
                if prev_oi > 0:
                    oi_change_pct = round(((oi_value - prev_oi) / prev_oi) * 100, 4)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass

        result = {
            "open_interest": round(oi_value, 2),
            "oi_change_pct": oi_change_pct,
        }

        await r.set("coinalyze:oi", json.dumps(result))
        logger.info("Stored Coinalyze OI: %.2f, change=%.4f%%", oi_value, oi_change_pct)

    except Exception as exc:
        logger.error("fetch_coinalyze_oi failed: %s", exc)


async def fetch_coinalyze_funding() -> None:
    """Fetch aggregated BTC funding rate from Coinalyze.

    Redis key ``coinalyze:funding`` structure:
      funding_rate   float  — latest aggregated funding rate
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            data = await _get(client, "/funding-rate", {
                "symbols": SYMBOL,
            })

        if not data or not isinstance(data, list) or len(data) == 0:
            return

        entry = data[0] if isinstance(data[0], dict) else {}
        rate = float(entry.get("value", 0) or 0)

        result = {
            "funding_rate": rate,
        }

        r = await get_redis()
        await r.set("coinalyze:funding", json.dumps(result))
        logger.info("Stored Coinalyze funding: %.6f", rate)

    except Exception as exc:
        logger.error("fetch_coinalyze_funding failed: %s", exc)


async def fetch_coinalyze_long_short() -> None:
    """Fetch global long/short ratio from Coinalyze.

    Redis key ``coinalyze:long_short`` structure:
      ratio       float  — long/short ratio (>1 = more longs, <1 = more shorts)
      long_pct    float  — percentage of accounts long
      short_pct   float  — percentage of accounts short
    """
    try:
        now = int(time.time())
        since = now - 2 * 3600

        async with httpx.AsyncClient(timeout=20) as client:
            data = await _get(client, "/long-short-ratio-history", {
                "symbols": SYMBOL,
                "interval": "1hour",
                "from": since,
                "to": now,
            })

        if not data or not isinstance(data, list) or len(data) == 0:
            return

        latest = data[-1] if isinstance(data[-1], dict) else {}
        ratio = float(latest.get("r", 1.0) or 1.0)  # 'r' = ratio

        # Convert ratio to percentages
        long_pct = round((ratio / (1 + ratio)) * 100, 2) if ratio > 0 else 50.0
        short_pct = round(100 - long_pct, 2)

        result = {
            "ratio": round(ratio, 4),
            "long_pct": long_pct,
            "short_pct": short_pct,
        }

        r = await get_redis()
        await r.set("coinalyze:long_short", json.dumps(result))
        logger.info("Stored Coinalyze L/S: ratio=%.4f, long=%.1f%%, short=%.1f%%", ratio, long_pct, short_pct)

    except Exception as exc:
        logger.error("fetch_coinalyze_long_short failed: %s", exc)
