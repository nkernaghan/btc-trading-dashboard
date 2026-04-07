"""APScheduler-based scheduler for all data fetchers."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from data.macro import fetch_macro
from data.coinglass import fetch_coinglass
from data.sentiment import fetch_btc_dominance, fetch_fear_greed, fetch_polymarket
from data.onchain import fetch_onchain
from data.news import fetch_news_api
from data.options import fetch_options_data
from data.geopolitical import fetch_geopolitical_events, fetch_geopolitical_tone, fetch_conflict_intensity
from data.okx import fetch_okx_funding, fetch_okx_open_interest
from data.coinalyze import (
    fetch_coinalyze_liquidations, fetch_coinalyze_oi,
    fetch_coinalyze_funding, fetch_coinalyze_long_short,
)
from data.free_onchain import (
    fetch_stablecoin_flows, fetch_defi_tvl, fetch_hashrate_difficulty,
    fetch_whale_transactions, fetch_btc_tx_volume,
)
from scoring.outcome_tracker import check_signal_outcomes

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Register all fetchers at appropriate intervals and start the scheduler."""
    global _scheduler

    _scheduler = AsyncIOScheduler()

    # 5-minute interval fetchers
    _scheduler.add_job(fetch_macro, "interval", minutes=5, id="macro", misfire_grace_time=60)
    _scheduler.add_job(fetch_coinglass, "interval", minutes=5, id="coinglass", misfire_grace_time=60)
    _scheduler.add_job(fetch_btc_dominance, "interval", minutes=5, id="btc_dominance", misfire_grace_time=60)
    _scheduler.add_job(fetch_polymarket, "interval", minutes=5, id="polymarket", misfire_grace_time=60)
    _scheduler.add_job(fetch_onchain, "interval", minutes=5, id="onchain", misfire_grace_time=60)
    _scheduler.add_job(fetch_news_api, "interval", minutes=5, id="news", misfire_grace_time=60)

    # OKX derivatives data (free, no key)
    _scheduler.add_job(fetch_okx_funding, "interval", minutes=5, id="okx_funding", misfire_grace_time=60)
    _scheduler.add_job(fetch_okx_open_interest, "interval", minutes=5, id="okx_oi", misfire_grace_time=60)

    # Coinalyze aggregated derivatives (free key, 40 req/min)
    _scheduler.add_job(fetch_coinalyze_liquidations, "interval", minutes=5, id="ca_liquidations", misfire_grace_time=60)
    _scheduler.add_job(fetch_coinalyze_oi, "interval", minutes=5, id="ca_oi", misfire_grace_time=60)
    _scheduler.add_job(fetch_coinalyze_funding, "interval", minutes=5, id="ca_funding", misfire_grace_time=60)
    _scheduler.add_job(fetch_coinalyze_long_short, "interval", minutes=5, id="ca_long_short", misfire_grace_time=60)

    # Free on-chain and DeFi data (no key)
    _scheduler.add_job(fetch_whale_transactions, "interval", minutes=5, id="whale_txs", misfire_grace_time=60)
    _scheduler.add_job(fetch_btc_tx_volume, "interval", minutes=15, id="btc_tx_volume", misfire_grace_time=120)
    _scheduler.add_job(fetch_stablecoin_flows, "interval", minutes=15, id="stablecoin_flows", misfire_grace_time=120)
    _scheduler.add_job(fetch_defi_tvl, "interval", minutes=15, id="defi_tvl", misfire_grace_time=120)
    _scheduler.add_job(fetch_hashrate_difficulty, "interval", minutes=15, id="hashrate", misfire_grace_time=120)

    # Geopolitical data (GDELT — free, no key)
    _scheduler.add_job(fetch_geopolitical_events, "interval", minutes=10, id="geopolitical_events", misfire_grace_time=120)
    _scheduler.add_job(fetch_geopolitical_tone, "interval", minutes=15, id="geopolitical_tone", misfire_grace_time=120)
    _scheduler.add_job(fetch_conflict_intensity, "interval", minutes=15, id="conflict_intensity", misfire_grace_time=120)

    # Signal outcome tracking (check if SL/TP hit)
    _scheduler.add_job(check_signal_outcomes, "interval", minutes=1, id="outcome_tracker", misfire_grace_time=30)

    # 15-minute interval fetchers
    _scheduler.add_job(fetch_fear_greed, "interval", minutes=15, id="fear_greed", misfire_grace_time=120)
    _scheduler.add_job(fetch_options_data, "interval", minutes=15, id="options", misfire_grace_time=120)

    _scheduler.start()
    logger.info("Scheduler started with %d jobs", len(_scheduler.get_jobs()))

    return _scheduler


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
