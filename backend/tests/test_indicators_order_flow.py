"""Tests for backend.indicators.order_flow."""

import numpy as np
import pytest

from backend.indicators.order_flow import (
    calc_bid_ask_spread_score,
    calc_cvd,
    calc_l4_depth_imbalance,
    calc_obv,
    calc_ofi,
    calc_volume_profile,
    calc_vpin,
)


def test_ofi_balanced():
    bids = [{"price": 67000, "size": 10}]
    asks = [{"price": 67001, "size": 10}]
    prev_bids = [{"price": 67000, "size": 10}]
    prev_asks = [{"price": 67001, "size": 10}]
    ofi = calc_ofi(bids, asks, prev_bids, prev_asks)
    assert ofi == 0.0


def test_ofi_buy_pressure():
    bids = [{"price": 67000, "size": 20}]
    asks = [{"price": 67001, "size": 10}]
    prev_bids = [{"price": 67000, "size": 10}]
    prev_asks = [{"price": 67001, "size": 10}]
    ofi = calc_ofi(bids, asks, prev_bids, prev_asks)
    assert ofi > 0


def test_vpin_range():
    np.random.seed(42)
    buys = np.random.uniform(100, 1000, 100)
    sells = np.random.uniform(100, 1000, 100)
    vpin = calc_vpin(buys, sells)
    assert 0 <= vpin <= 1


def test_spread_score():
    score = calc_bid_ask_spread_score(5.0, 10.0)
    assert 0 <= score <= 100
    # Tighter than average → high score
    assert score > 50


def test_cvd():
    trades = [
        {"side": "buy", "size": 100},
        {"side": "sell", "size": 40},
        {"side": "buy", "size": 60},
    ]
    cvd = calc_cvd(trades)
    assert cvd == 120.0  # 100 - 40 + 60


def test_obv():
    closes = np.array([100, 102, 101, 103, 104])
    volumes = np.array([1000, 1500, 1200, 1800, 2000])
    obv = calc_obv(closes, volumes)
    # up, down, up, up → +1500 -1200 +1800 +2000 = 4100
    assert obv == 4100.0


def test_volume_profile():
    np.random.seed(42)
    prices = np.random.normal(67000, 200, 500)
    volumes = np.random.uniform(100, 1000, 500)
    poc, vah, val = calc_volume_profile(prices, volumes)
    assert val <= poc <= vah


def test_l4_depth_imbalance():
    bids = [{"price": 67000 - i, "size": 10} for i in range(10)]
    asks = [{"price": 67001 + i, "size": 5} for i in range(10)]
    imbalance = calc_l4_depth_imbalance(bids, asks)
    # More bid size → positive
    assert imbalance > 0
    assert -1 <= imbalance <= 1
