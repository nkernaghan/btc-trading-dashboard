import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()
connected_clients: list[WebSocket] = []

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    logger.info(f"Client connected. Total: {len(connected_clients)}")
    try:
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("btc:trades", "btc:orderbook", "btc:candle", "btc:signal")

        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await ws.send_json({"channel": message["channel"], "data": json.loads(message["data"])})
                    except Exception:
                        break

        async def listen_client():
            async for data in ws.iter_json():
                logger.info(f"Client msg: {data}")

        await asyncio.gather(listen_redis(), listen_client())
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.remove(ws)

async def broadcast_signal(signal_data: dict):
    r = await get_redis()
    await r.publish("btc:signal", json.dumps(signal_data))
