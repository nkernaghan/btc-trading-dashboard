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
from redis_client import get_redis, set_with_ts

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
        await set_with_ts(r, "coinalyze:liquidations", json.dumps(result))
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

        # Last entry is most recent. Distinguish "field missing" from
        # "real zero" — a 0 OI on the Binance BTCUSDT perp is not
        # plausible, so any missing/zero/malformed value is treated as
        # a failed read and we skip the Redis write.
        latest = data[-1] if isinstance(data[-1], dict) else {}
        raw_oi = latest.get("o")
        if raw_oi is None:
            logger.warning("Coinalyze OI response missing 'o' field — skip")
            return
        try:
            oi_value = float(raw_oi)
        except (TypeError, ValueError):
            logger.warning("Coinalyze OI non-numeric 'o': %r", raw_oi)
            return
        if oi_value <= 0:
            logger.warning("Coinalyze OI returned non-positive value %.2f — skip", oi_value)
            return

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

        await set_with_ts(r, "coinalyze:oi", json.dumps(result))
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

        # A funding rate of exactly 0.0 is a valid reading (truly
        # neutral market), but a *missing* field is not — it would
        # silently vote as "neutral" when the reality is unknown.
        # Distinguish the two cases: skip the write only when the
        # field is absent or non-numeric.
        entry = data[0] if isinstance(data[0], dict) else {}
        raw_value = entry.get("value")
        if raw_value is None:
            logger.warning("Coinalyze funding response missing 'value' — skip")
            return
        try:
            rate = float(raw_value)
        except (TypeError, ValueError):
            logger.warning("Coinalyze funding non-numeric 'value': %r", raw_value)
            return

        result = {
            "funding_rate": rate,
        }

        r = await get_redis()
        await set_with_ts(r, "coinalyze:funding", json.dumps(result))
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

        # 1.0 is the "neutral" L/S ratio — falling back to it on a
        # missing field would silently look like real data showing a
        # balanced market. Distinguish missing from present.
        latest = data[-1] if isinstance(data[-1], dict) else {}
        raw_ratio = latest.get("r")
        if raw_ratio is None:
            logger.warning("Coinalyze L/S response missing 'r' — skip")
            return
        try:
            ratio = float(raw_ratio)
        except (TypeError, ValueError):
            logger.warning("Coinalyze L/S non-numeric 'r': %r", raw_ratio)
            return
        if ratio <= 0:
            logger.warning("Coinalyze L/S returned non-positive ratio %.4f — skip", ratio)
            return

        # Convert ratio to percentages
        long_pct = round((ratio / (1 + ratio)) * 100, 2)
        short_pct = round(100 - long_pct, 2)

        result = {
            "ratio": round(ratio, 4),
            "long_pct": long_pct,
            "short_pct": short_pct,
        }

        r = await get_redis()
        await set_with_ts(r, "coinalyze:long_short", json.dumps(result))
        logger.info("Stored Coinalyze L/S: ratio=%.4f, long=%.1f%%, short=%.1f%%", ratio, long_pct, short_pct)

    except Exception as exc:
        logger.error("fetch_coinalyze_long_short failed: %s", exc)
