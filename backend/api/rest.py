import json
from fastapi import APIRouter, Query
from redis_client import get_redis
from models.schemas import BacktestRequest
from db import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])

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

@router.post("/backtest")
async def run_backtest(request: BacktestRequest):
    return {"status": "backtest endpoint ready", "params": request.model_dump()}
