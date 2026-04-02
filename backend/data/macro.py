"""Macro data fetcher — DXY, SPX, NQ, US10Y, Gold via yfinance."""

import json
import logging

import yfinance as yf

from redis_client import get_redis

logger = logging.getLogger(__name__)

TICKERS = {
    "DXY": "DX-Y.NYB",
    "SPX": "^GSPC",
    "NQ": "^IXIC",
    "US10Y": "^TNX",
    "Gold": "GC=F",
}


async def fetch_macro():
    """Fetch macro indicators, compute price and change_pct, store in Redis."""
    try:
        results = {}

        for name, symbol in TICKERS.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", interval="1h")

                if hist.empty:
                    logger.warning("No data returned for %s (%s)", name, symbol)
                    continue

                current_price = float(hist["Close"].iloc[-1])
                open_price = float(hist["Close"].iloc[0])
                change_pct = ((current_price - open_price) / open_price) * 100.0

                results[name] = {
                    "symbol": symbol,
                    "price": round(current_price, 4),
                    "change_pct": round(change_pct, 4),
                }

            except Exception as e:
                logger.error("Error fetching %s: %s", name, e)

        if results:
            r = await get_redis()
            await r.set("macro:data", json.dumps(results))
            logger.info("Stored macro data for %d tickers", len(results))

    except Exception as e:
        logger.error("fetch_macro failed: %s", e)
