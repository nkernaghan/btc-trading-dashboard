"""Options data fetcher — Deribit put/call ratio, OI, max pain, IV."""

import json
import logging
import time
from datetime import datetime, timezone

import httpx

from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"

# Deribit option instruments are named BTC-DDMMMYY-STRIKE-C|P where the
# month is uppercase (e.g. BTC-28JUN24-70000-C). Python's %b is locale-
# dependent and upper/lower-case handling varies, so parse via explicit
# map for deterministic behavior.
_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_deribit_expiry(ddmmmyy: str) -> datetime | None:
    """Parse Deribit's DDMMMYY string (e.g. '28JUN24') as UTC expiry.

    Deribit options settle at 08:00 UTC on their expiry date; using
    that moment means the "future expiry" filter in max-pain drops a
    same-day expiry only after settlement rather than at midnight.
    """
    if not ddmmmyy or len(ddmmmyy) < 7:
        return None
    try:
        day = int(ddmmmyy[:2])
        month = _MONTH_ABBR.get(ddmmmyy[2:5].upper())
        year = 2000 + int(ddmmmyy[5:7])
        if month is None:
            return None
        return datetime(year, month, day, 8, 0, 0, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _compute_max_pain(
    contracts: list[tuple[float, float, bool]],
) -> float:
    """Return the strike that minimizes aggregate writer payout.

    ``contracts`` is a list of (strike, open_interest, is_call) tuples,
    all belonging to the SAME expiry. The candidate strike set is the
    set of strikes appearing in the contracts — payout is piecewise-
    linear between strikes and the minimum must occur at a breakpoint.

    For a candidate strike S and each open contract with strike K and
    open interest N:
      - call writer pays N * max(S - K, 0)
      - put writer pays  N * max(K - S, 0)

    Returns 0.0 if ``contracts`` is empty.
    """
    if not contracts:
        return 0.0
    strikes = sorted({c[0] for c in contracts})

    def payout_at(S: float) -> float:
        total = 0.0
        for strike, oi, is_call in contracts:
            if is_call:
                total += oi * max(S - strike, 0.0)
            else:
                total += oi * max(strike - S, 0.0)
        return total

    return min(strikes, key=payout_at)


async def fetch_options_data():
    """Fetch options data from Deribit: put/call ratio, per-expiry max
    pain strike (nearest future expiry), and implied volatility index.
    Store in Redis.

    ``put_call_ratio`` is aggregated across all expiries (overall
    sentiment). ``max_pain_strike`` is computed per expiry for the
    nearest future expiry — that's the expiry with the strongest
    dealer-gamma gravity and the one traders actually watch.
    """
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

        # Aggregate OI across all expiries for the put/call ratio, and
        # bucket contracts per-expiry for the max-pain computation.
        total_call_oi = 0.0
        total_put_oi = 0.0
        options_by_expiry: dict[datetime, list[tuple[float, float, bool]]] = {}

        for entry in book_data:
            instrument = entry.get("instrument_name", "")
            try:
                oi = float(entry.get("open_interest", 0) or 0)
            except (TypeError, ValueError):
                continue
            if oi <= 0:
                continue

            # Instrument format: BTC-DDMMMYY-STRIKE-C|P
            parts = instrument.split("-")
            if len(parts) != 4:
                continue
            _, expiry_str, strike_str, kind = parts

            expiry = _parse_deribit_expiry(expiry_str)
            if expiry is None:
                continue
            try:
                strike = float(strike_str)
            except (TypeError, ValueError):
                continue

            kind_upper = kind.upper()
            if kind_upper == "C":
                is_call = True
                total_call_oi += oi
            elif kind_upper == "P":
                is_call = False
                total_put_oi += oi
            else:
                continue

            options_by_expiry.setdefault(expiry, []).append((strike, oi, is_call))

        put_call_ratio = (
            total_put_oi / total_call_oi if total_call_oi > 0 else 0.0
        )

        # Max pain: pick the nearest future expiry and find the strike
        # that minimises aggregate writer payout. Fall back to 0.0 if
        # no future expiries are present — engine's ``max_pain > 0``
        # guard then skips the Max-Pain-Dist vote cleanly.
        now = datetime.now(timezone.utc)
        future_expiries = sorted(e for e in options_by_expiry if e > now)
        if future_expiries:
            nearest = future_expiries[0]
            max_pain_strike = _compute_max_pain(options_by_expiry[nearest])
            max_pain_expiry_iso: str | None = nearest.isoformat()
        else:
            max_pain_strike = 0.0
            max_pain_expiry_iso = None

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
            "max_pain_expiry": max_pain_expiry_iso,
            "iv_index": round(iv_index, 4),
        }

        r = await get_redis()
        await set_with_ts(r, "options:data", json.dumps(result))
        logger.info(
            "Stored options data: P/C=%.4f, max_pain=%s (expiry=%s), IV=%.2f",
            put_call_ratio,
            max_pain_strike,
            max_pain_expiry_iso or "none",
            iv_index,
        )

    except Exception as e:
        logger.error("fetch_options_data failed: %s", e)
