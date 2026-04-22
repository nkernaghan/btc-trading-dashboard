"""Sentiment data fetchers — Fear & Greed, BTC Dominance, Polymarket."""

import json
import logging
import re

import httpx

from config import settings
from redis_client import get_redis, set_with_ts


def _cg_headers() -> dict:
    """Return CoinGecko headers with API key if configured."""
    if settings.coingecko_api_key:
        return {"x-cg-demo-api-key": settings.coingecko_api_key}
    return {}

logger = logging.getLogger(__name__)


async def fetch_fear_greed():
    """Fetch Crypto Fear & Greed Index, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            resp.raise_for_status()
            data = resp.json()

        fng = data.get("data", [{}])[0]
        result = {
            "value": int(fng.get("value", 0)),
            "classification": fng.get("value_classification", "Unknown"),
            "timestamp": int(fng.get("timestamp", 0)),
        }

        r = await get_redis()
        await set_with_ts(r, "sentiment:fear_greed", json.dumps(result))
        logger.info("Stored Fear & Greed: %s (%s)", result["value"], result["classification"])

    except Exception as e:
        logger.error("fetch_fear_greed failed: %s", e)


async def fetch_btc_dominance():
    """Fetch BTC dominance from CoinGecko global API, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/global", headers=_cg_headers())
            resp.raise_for_status()
            data = resp.json()

        market_data = data.get("data", {})
        btc_dom = market_data.get("market_cap_percentage", {}).get("btc", 0.0)
        total_mcap = market_data.get("total_market_cap", {}).get("usd", 0.0)

        result = {
            "btc_dominance": round(btc_dom, 2),
            "total_market_cap_usd": total_mcap,
        }

        r = await get_redis()
        await set_with_ts(r, "sentiment:btc_dominance", json.dumps(result))
        logger.info("Stored BTC dominance: %.2f%%", btc_dom)

    except Exception as e:
        logger.error("fetch_btc_dominance failed: %s", e)


# Polymarket question framing — used to decide whether a high `yes_price`
# indicates a bullish or bearish outcome for BTC. A YES on "will BTC hit
# $120k" is bullish; a YES on "will BTC crash below $50k" is bearish.
#
# Direction keywords (above/below/under/over) are stronger than action
# keywords (break/hit/reach) because the direction word fully disambiguates
# framing even when the action word is neutral.
#
# All matching is word-boundary regex, not substring. Substring matching
# silently mis-classifies common cases: "over" inside "recover"/"discover"/
# "overturn", "ath" inside "death"/"cathedral"/"weather", "ban" inside
# "abandon". Because directional keywords outrank action keywords, a false
# directional hit flips the polarity — the exact failure this classifier
# is meant to prevent.
_POLY_DIRECTIONAL_BULL = ("above", "over", "exceed", "surpass", "higher")
_POLY_DIRECTIONAL_BEAR = ("below", "under", "lower")
_POLY_ACTION_BULL = (
    "reach", "hit", "break", "cross", "surge", "rally",
    "approve", "adoption", "new high", "all-time high", "ath",
    "new ath", "record high",
)
_POLY_ACTION_BEAR = (
    "crash", "fall", "drop", "plunge", "capitulate", "collapse",
    "tank", "dump", "lawsuit", "ban", "hack", "rug", "sec enforcement",
)


def _compile_wb(keywords: tuple[str, ...]) -> re.Pattern:
    """Compile keywords into a single case-insensitive word-boundary regex."""
    escaped = [re.escape(kw) for kw in keywords]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


_POLY_DIR_BULL_RE = _compile_wb(_POLY_DIRECTIONAL_BULL)
_POLY_DIR_BEAR_RE = _compile_wb(_POLY_DIRECTIONAL_BEAR)
_POLY_ACT_BULL_RE = _compile_wb(_POLY_ACTION_BULL)
_POLY_ACT_BEAR_RE = _compile_wb(_POLY_ACTION_BEAR)


def _classify_polarity(question: str) -> str:
    """Classify a Polymarket question as bull / bear / unknown framing.

    A "bull" classification means a high ``yes_price`` is bullish for BTC;
    a "bear" classification means a high ``yes_price`` is bearish. Unknown
    questions should be skipped by consumers rather than defaulted either
    way, since defaulting silently flips the sign of the signal.

    Directional keywords (above/below) win over action keywords (break/hit)
    because the direction word alone is sufficient to determine framing.
    """
    if not question:
        return "unknown"

    dir_bull = bool(_POLY_DIR_BULL_RE.search(question))
    dir_bear = bool(_POLY_DIR_BEAR_RE.search(question))
    if dir_bull and not dir_bear:
        return "bull"
    if dir_bear and not dir_bull:
        return "bear"

    act_bull = len(_POLY_ACT_BULL_RE.findall(question))
    act_bear = len(_POLY_ACT_BEAR_RE.findall(question))
    if act_bull > act_bear:
        return "bull"
    if act_bear > act_bull:
        return "bear"
    return "unknown"


async def fetch_polymarket():
    """Fetch crypto-related markets from Polymarket CLOB API, store in Redis."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use the CLOB API which doesn't require auth
            resp = await client.get(
                "https://clob.polymarket.com/markets",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Filter for crypto/BTC-related markets
        btc_keywords = ["bitcoin", "btc", "crypto", "ethereum", "eth"]
        markets = []
        raw_list = data if isinstance(data, list) else data.get("data", data.get("markets", []))
        for m in raw_list:
            question_raw = m.get("question", "") or ""
            question = question_raw.lower()
            if any(kw in question for kw in btc_keywords):
                # Extract probability from tokens if available
                tokens = m.get("tokens", [])
                yes_price = None
                if tokens and isinstance(tokens, list):
                    for t in tokens:
                        if t.get("outcome", "").lower() == "yes":
                            yes_price = float(t.get("price", 0))
                            break

                markets.append({
                    "question": question_raw,
                    "yes_price": yes_price,
                    "polarity": _classify_polarity(question_raw),
                    "volume": float(m.get("volume", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                    "active": m.get("active", True),
                })

        r = await get_redis()
        await set_with_ts(r, "sentiment:polymarket", json.dumps(markets))
        polarity_counts = {
            "bull": sum(1 for m in markets if m["polarity"] == "bull"),
            "bear": sum(1 for m in markets if m["polarity"] == "bear"),
            "unknown": sum(1 for m in markets if m["polarity"] == "unknown"),
        }
        logger.info(
            "Stored %d Polymarket crypto markets (bull=%d, bear=%d, unknown=%d)",
            len(markets), polarity_counts["bull"],
            polarity_counts["bear"], polarity_counts["unknown"],
        )

    except Exception as e:
        logger.error("fetch_polymarket failed: %s", e)
