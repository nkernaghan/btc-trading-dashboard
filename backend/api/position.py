import json
from datetime import datetime, timezone
from fastapi import APIRouter
from models.schemas import Position
from models.enums import Direction
from redis_client import get_redis
from db import get_db

router = APIRouter(prefix="/api/position", tags=["position"])

@router.post("/open")
async def open_position(entry_price: float, size: float, leverage: int, direction: str):
    pos = Position(entry_price=entry_price, size=size, leverage=leverage,
                   direction=Direction(direction), entry_time=datetime.now(timezone.utc))
    r = await get_redis()
    await r.set("position:active", pos.model_dump_json())
    db = await get_db()
    await db.execute(
        "INSERT INTO positions (entry_price, size, leverage, direction, entry_time) VALUES (?, ?, ?, ?, ?)",
        (pos.entry_price, pos.size, pos.leverage, pos.direction.value, pos.entry_time.isoformat()))
    await db.commit()
    await db.close()
    return {"status": "position opened", "position": pos.model_dump()}

@router.get("/active")
async def get_active_position():
    r = await get_redis()
    pos_json = await r.get("position:active")
    if not pos_json:
        return {"position": None}
    pos = Position.model_validate_json(pos_json)
    price_json = await r.get("btc:price")
    if price_json:
        price_data = json.loads(price_json)
        current_price = price_data.get("price", pos.entry_price)
        pos.current_price = current_price
        if pos.direction == Direction.LONG:
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            pos.liquidation_price = pos.entry_price * (1 - 1 / pos.leverage)
        else:
            pnl_pct = (pos.entry_price - current_price) / pos.entry_price
            pos.liquidation_price = pos.entry_price * (1 + 1 / pos.leverage)
        pos.unrealized_pnl_pct = round(pnl_pct * pos.leverage * 100, 2)
        pos.unrealized_pnl = round(pos.size * pnl_pct * pos.leverage, 2)
        pos.distance_to_liq_pct = round(abs(current_price - pos.liquidation_price) / current_price * 100, 2)
        pos.breakeven_price = pos.entry_price + (pos.accumulated_funding or 0) / (pos.size / pos.entry_price)
    return {"position": pos.model_dump()}

@router.post("/close")
async def close_position():
    r = await get_redis()
    pos_json = await r.get("position:active")
    if not pos_json:
        return {"status": "no active position"}
    await r.delete("position:active")
    return {"status": "position closed"}
