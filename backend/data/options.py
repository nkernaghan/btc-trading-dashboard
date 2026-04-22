"""Options data fetcher — Deribit put/call ratio, OI, max pain, IV."""

import json
import logging
import time

import httpx

from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"


async def fetch_options_data():
    """Fetch options data from Deribit: book summaries for put/call ratio,
    open interest, max pain strike, and implied volatility index.
    Store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Fetch option book summaries
            book_resp = await client.get(
                f"{DERIBIT_BASE}/get_book_summary_by_currency",
                params={"currency": "BTC", "kind": "option"},
            )
            book_resp.raise_for_status()
            book_data = book_resp.json().get("result", [])

            # Fetch volatility index (requires start/end timestamps)
            now_ms = int(time.time() * 1000)
            one_day_ago_ms = now_ms - 86_400_000
            vol_resp = await client.get(
                f"{DERIBIT_BASE}/get_volatility_index_data",
                params={
                    "currency": "BTC",
                    "resolution": 3600,
                    "start_timestamp": one_day_ago_ms,
                    "end_timestamp": now_ms,
                },
            )
            vol_resp.raise_for_status()
            vol_data = vol_resp.json().get("result", {})

        # Compute put/call ratio and open interest
        total_call_oi = 0.0
        total_put_oi = 0.0
        strike_oi: dict[float, float] = {}  # strike -> net OI for max pain

        for entry in book_data:
            instrument = entry.get("instrument_name", "")
            oi = float(entry.get("open_interest", 0))

            # Extract strike from instrument name (e.g., BTC-28JUN24-70000-C)
            parts = instrument.split("-")
            if len(parts) >= 4:
                try:
                    strike = float(parts[2])
                except ValueError:
                    continue

                option_type = parts[3]  # C or P

                if option_type == "C":
                    total_call_oi += oi
                elif option_type == "P":
                    total_put_oi += oi

                strike_oi[strike] = strike_oi.get(strike, 0) + oi

        put_call_ratio = (
            total_put_oi / total_call_oi if total_call_oi > 0 else 0.0
        )

        # Max pain: strike with highest total open interest
        max_pain_strike = (
            max(strike_oi, key=strike_oi.get) if strike_oi else 0.0
        )

        # IV index from volatility data
        iv_index = 0.0
        vol_points = vol_data.get("data", [])
        if vol_points:
            # Last data point: [timestamp, open, high, low, close]
            last_point = vol_points[-1]
            if isinstance(last_point, list) and len(last_point) >= 5:
                iv_index = float(last_point[4])  # close value

        result = {
            "put_call_ratio": round(put_call_ratio, 4),
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "max_pain_strike": max_pain_strike,
            "iv_index": round(iv_index, 4),
        }

        r = await get_redis()
        await set_with_ts(r, "options:data", json.dumps(result))
        logger.info(
            "Stored options data: P/C=%.4f, max_pain=%s, IV=%.2f",
            put_call_ratio,
            max_pain_strike,
            iv_index,
        )

    except Exception as e:
        logger.error("fetch_options_data failed: %s", e)
