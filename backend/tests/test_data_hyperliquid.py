"""Tests for Hyperliquid WebSocket parse functions."""

import pytest

from data.hyperliquid_ws import parse_candle_msg, parse_l2_msg, parse_trade_msg


def test_parse_trade_msg():
    raw = {
        "channel": "trades",
        "data": [
            {
                "coin": "BTC",
                "side": "B",
                "px": "67243.5",
                "sz": "0.5",
                "time": 1700000000000,
            }
        ],
    }
    trades = parse_trade_msg(raw)
    assert len(trades) == 1
    assert trades[0]["price"] == 67243.5
    assert trades[0]["size"] == 0.5
    assert trades[0]["side"] == "buy"
    assert trades[0]["timestamp"] == 1700000000000


def test_parse_trade_msg_sell():
    raw = {
        "channel": "trades",
        "data": [
            {
                "coin": "BTC",
                "side": "A",
                "px": "67200.0",
                "sz": "1.0",
                "time": 1700000001000,
            }
        ],
    }
    trades = parse_trade_msg(raw)
    assert len(trades) == 1
    assert trades[0]["side"] == "sell"


def test_parse_trade_msg_multiple():
    raw = {
        "channel": "trades",
        "data": [
            {"coin": "BTC", "side": "B", "px": "67243.5", "sz": "0.5", "time": 1700000000000},
            {"coin": "BTC", "side": "A", "px": "67240.0", "sz": "1.2", "time": 1700000000100},
        ],
    }
    trades = parse_trade_msg(raw)
    assert len(trades) == 2


def test_parse_trade_msg_empty():
    raw = {"channel": "trades", "data": []}
    trades = parse_trade_msg(raw)
    assert len(trades) == 0


def test_parse_l2_msg():
    raw = {
        "channel": "l2Book",
        "data": {
            "coin": "BTC",
            "levels": [
                [{"px": "67240.0", "sz": "1.2", "n": 3}],
                [{"px": "67245.0", "sz": "0.9", "n": 2}],
            ],
        },
    }
    book = parse_l2_msg(raw)
    assert book["bids"][0]["price"] == 67240.0
    assert book["bids"][0]["size"] == 1.2
    assert book["asks"][0]["price"] == 67245.0
    assert book["asks"][0]["size"] == 0.9
    assert book["spread"] == pytest.approx(5.0)
    assert book["mid_price"] == pytest.approx(67242.5)


def test_parse_l2_msg_multiple_levels():
    raw = {
        "channel": "l2Book",
        "data": {
            "coin": "BTC",
            "levels": [
                [
                    {"px": "67240.0", "sz": "1.2", "n": 3},
                    {"px": "67235.0", "sz": "2.0", "n": 5},
                ],
                [
                    {"px": "67245.0", "sz": "0.9", "n": 2},
                    {"px": "67250.0", "sz": "1.5", "n": 4},
                ],
            ],
        },
    }
    book = parse_l2_msg(raw)
    assert len(book["bids"]) == 2
    assert len(book["asks"]) == 2


def test_parse_candle_msg():
    raw = {
        "channel": "candle",
        "data": {
            "t": 1700000000000,
            "o": "67200.0",
            "h": "67500.0",
            "l": "67100.0",
            "c": "67243.5",
            "v": "1234.5",
        },
    }
    candle = parse_candle_msg(raw)
    assert candle["timestamp"] == 1700000000000
    assert candle["open"] == 67200.0
    assert candle["high"] == 67500.0
    assert candle["low"] == 67100.0
    assert candle["close"] == 67243.5
    assert candle["volume"] == 1234.5
