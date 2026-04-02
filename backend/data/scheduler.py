"""APScheduler-based scheduler for all data fetchers."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from data.macro import fetch_macro
from data.coinglass import fetch_coinglass
from data.sentiment import fetch_btc_dominance, fetch_fear_greed, fetch_polymarket
from data.onchain import fetch_onchain, fetch_stablecoin_reserves
from data.news import fetch_news_api, fetch_etf_flows
from data.options import fetch_options_data

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
    _scheduler.add_job(fetch_stablecoin_reserves, "interval", minutes=5, id="stablecoin", misfire_grace_time=60)
    _scheduler.add_job(fetch_news_api, "interval", minutes=5, id="news", misfire_grace_time=60)

    # 15-minute interval fetchers
    _scheduler.add_job(fetch_fear_greed, "interval", minutes=15, id="fear_greed", misfire_grace_time=120)
    _scheduler.add_job(fetch_options_data, "interval", minutes=15, id="options", misfire_grace_time=120)
    _scheduler.add_job(fetch_etf_flows, "interval", minutes=15, id="etf_flows", misfire_grace_time=120)

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
