"""Hyperliquid WebSocket client for real-time BTC market data."""

import asyncio
import json
import logging
import time
from typing import Any

import websockets

from redis_client import get_redis

logger = logging.getLogger(__name__)

WS_URL = "wss://api.hyperliquid.xyz/ws"


def parse_trade_msg(msg: dict) -> list[dict]:
    """Parse trades from Hyperliquid WS message.

    Returns list of {price, size, side, timestamp}.
    """
    trades = []
    for t in msg.get("data", []):
        trades.append(
            {
                "price": float(t["px"]),
                "size": float(t["sz"]),
                "side": "buy" if t["side"] == "B" else "sell",
                "timestamp": int(t["time"]),
            }
        )
    return trades


def parse_l2_msg(msg: dict) -> dict:
    """Parse L2 order book from Hyperliquid WS message.

    Returns {bids, asks, spread, mid_price}.
    """
    data = msg.get("data", {})
    levels = data.get("levels", [[], []])

    bids = [
        {"price": float(lv["px"]), "size": float(lv["sz"]), "count": int(lv["n"])}
        for lv in levels[0]
    ]
    asks = [
        {"price": float(lv["px"]), "size": float(lv["sz"]), "count": int(lv["n"])}
        for lv in levels[1]
    ]

    best_bid = bids[0]["price"] if bids else 0.0
    best_ask = asks[0]["price"] if asks else 0.0
    spread = best_ask - best_bid
    mid_price = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0

    return {
        "bids": bids,
        "asks": asks,
        "spread": spread,
        "mid_price": mid_price,
    }


def parse_candle_msg(msg: dict) -> dict:
    """Parse candle from Hyperliquid WS message.

    Returns {timestamp, open, high, low, close, volume}.
    """
    d = msg.get("data", {})
    return {
        "timestamp": int(d["t"]),
        "open": float(d["o"]),
        "high": float(d["h"]),
        "low": float(d["l"]),
        "close": float(d["c"]),
        "volume": float(d["v"]),
    }


async def run_hyperliquid_ws():
    """Main async loop: connect to Hyperliquid WS, subscribe to BTC channels,
    parse messages, and push data to Redis."""

    subscriptions = [
        {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}},
        {"method": "subscribe", "subscription": {"type": "l2Book", "coin": "BTC"}},
        {
            "method": "subscribe",
            "subscription": {"type": "candle", "coin": "BTC", "interval": "1h"},
        },
    ]

    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                logger.info("Connected to Hyperliquid WebSocket")

                for sub in subscriptions:
                    await ws.send(json.dumps(sub))
                    logger.debug("Subscribed: %s", sub["subscription"]["type"])

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        channel = msg.get("channel", "")
                        r = await get_redis()

                        if channel == "trades":
                            trades = parse_trade_msg(msg)
                            if trades:
                                latest = trades[-1]
                                await r.set(
                                    "btc:price", json.dumps(latest)
                                )
                                await r.publish(
                                    "btc:price:stream", json.dumps(trades)
                                )

                        elif channel == "l2Book":
                            book = parse_l2_msg(msg)
                            await r.set("btc:orderbook", json.dumps(book))
                            await r.publish(
                                "btc:orderbook:stream", json.dumps(book)
                            )

                        elif channel == "candle":
                            candle = parse_candle_msg(msg)
                            await r.set(
                                "btc:candle:1h", json.dumps(candle)
                            )
                            await r.publish(
                                "btc:candle:stream", json.dumps(candle)
                            )

                    except Exception as e:
                        logger.error("Error processing WS message: %s", e)

        except websockets.ConnectionClosed as e:
            logger.warning("WS connection closed (%s), reconnecting in 5s", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("WS error: %s, reconnecting in 10s", e)
            await asyncio.sleep(10)
