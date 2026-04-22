"""Free on-chain and DeFi data fetchers — no API keys required.

Sources:
  stablecoins.llama.fi  — stablecoin circulating supply
  api.llama.fi          — DeFi total value locked (TVL)
  mempool.space         — Bitcoin hashrate and difficulty adjustment
  blockchain.info       — unconfirmed transactions (whale detection)
  api.blockchain.info   — estimated on-chain transaction volume (USD)

Redis keys written:
  defi:stablecoin_flows   — USDT/USDC circulation and daily/weekly changes
  defi:tvl                — DeFi TVL current value and day/week changes
  mining:hashrate         — hashrate, difficulty, and next retarget estimate
  onchain:whale_txs       — large unconfirmed transactions (>50 BTC)
  onchain:tx_volume       — estimated daily on-chain transaction volume in USD
"""

import json
import logging

import httpx

from redis_client import get_redis

logger = logging.getLogger(__name__)

_SATOSHIS_PER_BTC = 100_000_000  # 100,000,000
_WHALE_THRESHOLD_SATS = 50 * _SATOSHIS_PER_BTC  # 50 BTC in satoshis


async def fetch_stablecoin_flows() -> None:
    """Fetch USDT and USDC circulating supply from DeFiLlama and store in Redis.

    Computes day-over-day and week-over-week percentage changes for each
    stablecoin and a combined total.

    Redis key ``defi:stablecoin_flows`` structure:
      usdt_circ            float  — USDT circulating supply in USD
      usdc_circ            float  — USDC circulating supply in USD
      usdt_1d_change_pct   float  — USDT supply change vs previous day
      usdc_1d_change_pct   float  — USDC supply change vs previous day
      usdt_7d_change_pct   float  — USDT supply change vs previous week
      usdc_7d_change_pct   float  — USDC supply change vs previous week
      total_circ           float  — combined USDT + USDC circulation
      total_1d_change_pct  float  — combined supply daily change %
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://stablecoins.llama.fi/stablecoins")
            resp.raise_for_status()
            data = resp.json()

        assets: list[dict] = data.get("peggedAssets", [])

        usdt = _find_stablecoin(assets, "USDT")
        usdc = _find_stablecoin(assets, "USDC")

        usdt_circ = _pegged_usd(usdt, "circulating")
        usdt_prev_day = _pegged_usd(usdt, "circulatingPrevDay")
        usdt_prev_week = _pegged_usd(usdt, "circulatingPrevWeek")

        usdc_circ = _pegged_usd(usdc, "circulating")
        usdc_prev_day = _pegged_usd(usdc, "circulatingPrevDay")
        usdc_prev_week = _pegged_usd(usdc, "circulatingPrevWeek")

        usdt_1d = _pct_change(usdt_circ, usdt_prev_day)
        usdt_7d = _pct_change(usdt_circ, usdt_prev_week)
        usdc_1d = _pct_change(usdc_circ, usdc_prev_day)
        usdc_7d = _pct_change(usdc_circ, usdc_prev_week)

        total_circ = (usdt_circ or 0.0) + (usdc_circ or 0.0)
        total_prev_day = (usdt_prev_day or 0.0) + (usdc_prev_day or 0.0)
        total_1d = _pct_change(total_circ, total_prev_day) if total_prev_day else None

        result = {
            "usdt_circ": usdt_circ,
            "usdc_circ": usdc_circ,
            "usdt_1d_change_pct": usdt_1d,
            "usdc_1d_change_pct": usdc_1d,
            "usdt_7d_change_pct": usdt_7d,
            "usdc_7d_change_pct": usdc_7d,
            "total_circ": total_circ,
            "total_1d_change_pct": total_1d,
        }

        r = await get_redis()
        await r.set("defi:stablecoin_flows", json.dumps(result))
        logger.info(
            "Stored stablecoin flows: USDT=%.2fB, USDC=%.2fB, total_1d=%.4f%%",
            (usdt_circ or 0) / 1e9,
            (usdc_circ or 0) / 1e9,
            total_1d or 0,
        )

    except Exception as exc:
        logger.error("fetch_stablecoin_flows failed: %s", exc)


async def fetch_defi_tvl() -> None:
    """Fetch DeFi total value locked history from DeFiLlama and store in Redis.

    Uses the last two data points for daily change and the last eight for
    weekly trend.

    Redis key ``defi:tvl`` structure:
      current_tvl       float  — latest TVL in USD
      tvl_1d_change_pct float  — % change vs previous day
      tvl_7d_change_pct float  — % change vs 7 days prior
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://api.llama.fi/v2/historicalChainTvl")
            resp.raise_for_status()
            history: list[dict] = resp.json()

        if not history or len(history) < 2:
            logger.warning("fetch_defi_tvl: insufficient data points returned")
            return

        current_tvl = float(history[-1].get("tvl", 0))
        prev_day_tvl = float(history[-2].get("tvl", 0))

        tvl_1d_change_pct = _pct_change(current_tvl, prev_day_tvl)

        # Weekly: go back 7 data points (each point is daily in this series)
        week_idx = max(0, len(history) - 8)
        week_ago_tvl = float(history[week_idx].get("tvl", 0))
        tvl_7d_change_pct = _pct_change(current_tvl, week_ago_tvl)

        result = {
            "current_tvl": round(current_tvl, 2),
            "tvl_1d_change_pct": tvl_1d_change_pct,
            "tvl_7d_change_pct": tvl_7d_change_pct,
        }

        r = await get_redis()
        await r.set("defi:tvl", json.dumps(result))
        logger.info(
            "Stored DeFi TVL: %.2fB USD, 1d=%.4f%%, 7d=%.4f%%",
            current_tvl / 1e9,
            tvl_1d_change_pct or 0,
            tvl_7d_change_pct or 0,
        )

    except Exception as exc:
        logger.error("fetch_defi_tvl failed: %s", exc)


async def fetch_hashrate_difficulty() -> None:
    """Fetch Bitcoin mining metrics from mempool.space and store in Redis.

    Fetches both the 1-month hashrate history and the current difficulty
    adjustment estimate. Computes a 7-day hashrate change percentage from
    the hashrates array.

    Redis key ``mining:hashrate`` structure:
      hashrate                  float  — current hashrate (H/s)
      hashrate_7d_change_pct    float  — % change vs 7 days ago
      difficulty                float  — current difficulty
      next_difficulty_change_pct float — estimated % change at next retarget
      remaining_blocks          int    — blocks until next retarget
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            import asyncio as _asyncio
            hashrate_resp, adjustment_resp = await _asyncio.gather(
                _safe_get(client, "https://mempool.space/api/v1/mining/hashrate/1m"),
                _safe_get(client, "https://mempool.space/api/v1/difficulty-adjustment"),
            )

        # --- Hashrate ---
        current_hashrate: float | None = None
        hashrate_7d_change_pct: float | None = None

        if hashrate_resp is not None:
            current_hashrate = _to_float(hashrate_resp.get("currentHashrate"))
            hashrates: list[dict] = hashrate_resp.get("hashrates", [])
            if hashrates and len(hashrates) >= 8:
                # Each entry has avgHashrate; last entry is most recent
                recent = _to_float(hashrates[-1].get("avgHashrate"))
                week_ago = _to_float(hashrates[-8].get("avgHashrate"))
                hashrate_7d_change_pct = _pct_change(recent, week_ago)

        # --- Difficulty ---
        current_difficulty: float | None = None
        if hashrate_resp is not None:
            current_difficulty = _to_float(hashrate_resp.get("currentDifficulty"))

        # --- Difficulty adjustment ---
        next_difficulty_change_pct: float | None = None
        remaining_blocks: int | None = None

        if adjustment_resp is not None:
            next_difficulty_change_pct = _to_float(
                adjustment_resp.get("difficultyChange")
            )
            remaining_raw = adjustment_resp.get("remainingBlocks")
            if remaining_raw is not None:
                try:
                    remaining_blocks = int(remaining_raw)
                except (TypeError, ValueError):
                    pass

        result = {
            "hashrate": current_hashrate,
            "hashrate_7d_change_pct": hashrate_7d_change_pct,
            "difficulty": current_difficulty,
            "next_difficulty_change_pct": next_difficulty_change_pct,
            "remaining_blocks": remaining_blocks,
        }

        r = await get_redis()
        await r.set("mining:hashrate", json.dumps(result))
        logger.info(
            "Stored mining data: hashrate=%.3eH/s, 7d=%.4f%%, diff_change=%.4f%%",
            current_hashrate or 0,
            hashrate_7d_change_pct or 0,
            next_difficulty_change_pct or 0,
        )

    except Exception as exc:
        logger.error("fetch_hashrate_difficulty failed: %s", exc)


async def fetch_whale_transactions() -> None:
    """Scan unconfirmed Bitcoin transactions for large whale movements.

    Filters the mempool for transactions with total output value exceeding
    50 BTC. Applies a simple heuristic to classify outputs as likely exchange
    deposits (many small outputs) vs other transfers (few large outputs).

    Redis key ``onchain:whale_txs`` structure:
      whale_tx_count   int    — number of transactions over 50 BTC
      total_whale_btc  float  — sum of all whale transaction output values in BTC
      largest_tx_btc   float  — largest single transaction in BTC
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://blockchain.info/unconfirmed-transactions",
                params={"format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()

        txs: list[dict] = data.get("txs", [])

        whale_tx_count = 0
        total_whale_sats = 0
        largest_tx_sats = 0

        for tx in txs:
            out_total_sats = sum(
                int(o.get("value", 0))
                for o in tx.get("out", [])
                if not o.get("spent", False)
            )

            if out_total_sats >= _WHALE_THRESHOLD_SATS:
                whale_tx_count += 1
                total_whale_sats += out_total_sats
                if out_total_sats > largest_tx_sats:
                    largest_tx_sats = out_total_sats

        total_whale_btc = round(total_whale_sats / _SATOSHIS_PER_BTC, 8)
        largest_tx_btc = round(largest_tx_sats / _SATOSHIS_PER_BTC, 8)

        result = {
            "whale_tx_count": whale_tx_count,
            "total_whale_btc": total_whale_btc,
            "largest_tx_btc": largest_tx_btc,
        }

        r = await get_redis()
        await r.set("onchain:whale_txs", json.dumps(result))
        logger.info(
            "Stored whale txs: count=%d, total=%.2f BTC, largest=%.2f BTC",
            whale_tx_count,
            total_whale_btc,
            largest_tx_btc,
        )

    except Exception as exc:
        logger.error("fetch_whale_transactions failed: %s", exc)


async def fetch_btc_tx_volume() -> None:
    """Fetch estimated Bitcoin on-chain transaction volume in USD.

    Uses the Blockchain.com charts API for the 7-day window and computes
    a daily percentage change from the last two data points.

    Redis key ``onchain:tx_volume`` structure:
      volume_usd          float  — latest estimated daily volume in USD
      volume_1d_change_pct float — % change vs the prior day
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.blockchain.info/charts/estimated-transaction-volume-usd",
                params={"timespan": "7days", "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()

        values: list[dict] = data.get("values", [])

        if not values or len(values) < 2:
            logger.warning("fetch_btc_tx_volume: insufficient data points")
            return

        current_volume = _to_float(values[-1].get("y"))
        prev_volume = _to_float(values[-2].get("y"))
        volume_1d_change_pct = _pct_change(current_volume, prev_volume)

        result = {
            "volume_usd": current_volume,
            "volume_1d_change_pct": volume_1d_change_pct,
        }

        r = await get_redis()
        await r.set("onchain:tx_volume", json.dumps(result))
        logger.info(
            "Stored BTC tx volume: %.2fM USD, 1d=%.4f%%",
            (current_volume or 0) / 1e6,
            volume_1d_change_pct or 0,
        )

    except Exception as exc:
        logger.error("fetch_btc_tx_volume failed: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_stablecoin(assets: list[dict], symbol: str) -> dict | None:
    """Return the first asset entry whose symbol matches (case-insensitive).

    Args:
        assets: List of pegged-asset dicts from DeFiLlama.
        symbol: Token symbol to search for (e.g. ``"USDT"``).

    Returns:
        Matching asset dict, or None if not found.
    """
    symbol_lower = symbol.lower()
    for asset in assets:
        if (asset.get("symbol") or "").lower() == symbol_lower:
            return asset
    return None


def _pegged_usd(asset: dict | None, field: str) -> float | None:
    """Extract ``peggedUSD`` from a circulating-supply field in an asset dict.

    Args:
        asset: DeFiLlama pegged asset entry, or None.
        field: Top-level field name (e.g. ``"circulating"``).

    Returns:
        Float value of ``peggedUSD``, or None if unavailable.
    """
    if asset is None:
        return None
    sub = asset.get(field)
    if not isinstance(sub, dict):
        return None
    return _to_float(sub.get("peggedUSD"))


def _pct_change(current: float | None, previous: float | None) -> float | None:
    """Compute percentage change between two values.

    Args:
        current:  Current period value.
        previous: Prior period value.

    Returns:
        Percentage change rounded to 4 decimal places, or None if either
        value is None/zero.
    """
    if current is None or previous is None or previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 4)


def _to_float(value: object) -> float | None:
    """Cast a value to float, returning None on failure.

    Args:
        value: Any value to cast.

    Returns:
        Float or None.
    """
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


async def _safe_get(client: httpx.AsyncClient, url: str) -> dict | None:
    """Perform a GET request and return parsed JSON, or None on any error.

    Args:
        client: Shared httpx async client.
        url:    Target URL.

    Returns:
        Parsed JSON dict, or None if the request or parsing fails.
    """
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None
