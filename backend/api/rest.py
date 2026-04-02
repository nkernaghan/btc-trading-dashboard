import json
import httpx
from fastapi import APIRouter, Query
from redis_client import get_redis
from models.schemas import BacktestRequest
from db import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])

INTERVAL_MAP = {
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
}

@router.get("/price")
async def get_price():
    r = await get_redis()
    price = await r.get("btc:price")
    return json.loads(price) if price else {"price": 0}

@router.get("/indicators")
async def get_indicators():
    r = await get_redis()
    keys = ["macro:data", "onchain:data", "sentiment:fear_greed", "sentiment:btc_dominance",
            "sentiment:polymarket", "options:data", "coinglass:data", "news:articles", "etf:flows"]
    result = {}
    for key in keys:
        val = await r.get(key)
        if val:
            result[key.replace(":", "_")] = json.loads(val)
    return result

@router.get("/orderbook")
async def get_orderbook():
    r = await get_redis()
    book = await r.get("btc:orderbook")
    return json.loads(book) if book else {"bids": [], "asks": []}

@router.get("/signal")
async def get_signal():
    r = await get_redis()
    signal = await r.get("btc:signal:latest")
    votes = await r.get("btc:votes:latest")
    return {
        "signal": json.loads(signal) if signal else None,
        "votes": json.loads(votes) if votes else [],
    }

@router.get("/signals/history")
async def get_signal_history(limit: int = Query(50, le=500)):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

@router.get("/candles")
async def get_candles(timeframe: str = "1H", limit: int = 200):
    """Fetch historical candles from Hyperliquid REST API."""
    import time
    interval = INTERVAL_MAP.get(timeframe, "1h")
    # Calculate time range based on interval
    interval_ms = {"1h": 3600_000, "4h": 14400_000, "1d": 86400_000, "1w": 604800_000}
    ms_per_candle = interval_ms.get(interval, 3600_000)
    now = int(time.time() * 1000)
    start = now - (limit * ms_per_candle)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.hyperliquid.xyz/info",
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": interval,
                        "startTime": start,
                        "endTime": now,
                    }
                }
            )
            if resp.status_code == 200:
                raw = resp.json()
                candles = []
                for c in raw[-limit:]:
                    candles.append({
                        "time": int(c["t"]) // 1000,
                        "open": float(c["o"]),
                        "high": float(c["h"]),
                        "low": float(c["l"]),
                        "close": float(c["c"]),
                        "volume": float(c["v"]),
                    })
                return candles
    except Exception as e:
        return {"error": str(e)}
    return []


@router.post("/backtest")
async def run_backtest(request: BacktestRequest):
    return {"status": "backtest endpoint ready", "params": request.model_dump()}
