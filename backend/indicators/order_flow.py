"""Order-flow indicators — pure computation, no I/O."""

import numpy as np


def calc_ofi(
    bids: list[dict],
    asks: list[dict],
    prev_bids: list[dict],
    prev_asks: list[dict],
) -> float:
    """Order Flow Imbalance. Positive = net buy pressure.

    Each bid/ask dict: {"price": float, "size": float}
    """
    def _total_size(levels: list[dict]) -> float:
        return sum(l.get("size", 0.0) for l in levels)

    cur_bid = _total_size(bids)
    cur_ask = _total_size(asks)
    prev_bid = _total_size(prev_bids)
    prev_ask = _total_size(prev_asks)

    delta_bid = cur_bid - prev_bid
    delta_ask = cur_ask - prev_ask

    # OFI = change in bid depth minus change in ask depth
    return delta_bid - delta_ask


def calc_vpin(
    buy_volumes: np.ndarray, sell_volumes: np.ndarray, bucket_size: int = 50
) -> float:
    """Volume-synchronized Probability of Informed Trading (0-1).

    Operates on pre-bucketed buy/sell volume arrays.
    """
    n = min(len(buy_volumes), len(sell_volumes), bucket_size)
    if n == 0:
        return 0.5
    buys = buy_volumes[-n:]
    sells = sell_volumes[-n:]
    total = buys + sells
    total_sum = float(np.sum(total))
    if total_sum == 0:
        return 0.5
    imbalance = float(np.sum(np.abs(buys - sells)))
    vpin = imbalance / total_sum
    return float(np.clip(vpin, 0.0, 1.0))


def calc_bid_ask_spread_score(spread_bps: float, avg_spread_bps: float) -> float:
    """Score 0-100. Lower spread relative to average = higher score (tighter = better)."""
    if avg_spread_bps <= 0:
        return 50.0
    ratio = spread_bps / avg_spread_bps
    # ratio < 1 means tighter than average → high score
    # ratio > 2 means very wide → low score
    score = max(0.0, min(100.0, 100.0 * (1.0 - (ratio - 1.0))))
    return score


def calc_cvd(trades: list[dict]) -> float:
    """Cumulative Volume Delta from a list of trades.

    Each trade dict: {"side": "buy"|"sell", "size": float}
    """
    cvd = 0.0
    for t in trades:
        size = t.get("size", 0.0)
        if t.get("side") == "buy":
            cvd += size
        else:
            cvd -= size
    return cvd


def calc_obv(closes: np.ndarray, volumes: np.ndarray) -> float:
    """On-Balance Volume — returns final cumulative OBV value."""
    if len(closes) < 2:
        return 0.0
    obv = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += float(volumes[i])
        elif closes[i] < closes[i - 1]:
            obv -= float(volumes[i])
    return obv


def calc_volume_profile(
    prices: np.ndarray, volumes: np.ndarray, num_bins: int = 20
) -> tuple[float, float, float]:
    """Volume Profile → (POC, VAH, VAL).

    POC  = Point of Control (price level with most volume)
    VAH  = Value Area High (upper bound of 70% volume)
    VAL  = Value Area Low  (lower bound of 70% volume)
    """
    if len(prices) == 0:
        return 0.0, 0.0, 0.0

    price_min, price_max = float(np.min(prices)), float(np.max(prices))
    if price_min == price_max:
        return price_min, price_min, price_min

    bin_edges = np.linspace(price_min, price_max, num_bins + 1)
    bin_volumes = np.zeros(num_bins)

    indices = np.digitize(prices, bin_edges) - 1
    indices = np.clip(indices, 0, num_bins - 1)
    for i in range(len(prices)):
        bin_volumes[indices[i]] += float(volumes[i])

    # POC
    poc_idx = int(np.argmax(bin_volumes))
    poc = float((bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2.0)

    # Value Area (70% of total volume centered on POC)
    total_vol = float(np.sum(bin_volumes))
    target = total_vol * 0.7
    accumulated = float(bin_volumes[poc_idx])
    lo_idx, hi_idx = poc_idx, poc_idx

    while accumulated < target and (lo_idx > 0 or hi_idx < num_bins - 1):
        expand_lo = float(bin_volumes[lo_idx - 1]) if lo_idx > 0 else -1.0
        expand_hi = float(bin_volumes[hi_idx + 1]) if hi_idx < num_bins - 1 else -1.0
        if expand_lo >= expand_hi:
            lo_idx -= 1
            accumulated += float(bin_volumes[lo_idx])
        else:
            hi_idx += 1
            accumulated += float(bin_volumes[hi_idx])

    val = float(bin_edges[lo_idx])
    vah = float(bin_edges[hi_idx + 1])
    return poc, vah, val


def calc_l4_depth_imbalance(
    bids: list[dict], asks: list[dict], depth_levels: int = 10
) -> float:
    """Depth imbalance from -1 (ask heavy) to +1 (bid heavy).

    Each bid/ask dict: {"price": float, "size": float}
    """
    bid_sizes = sorted(bids, key=lambda x: x.get("price", 0), reverse=True)[:depth_levels]
    ask_sizes = sorted(asks, key=lambda x: x.get("price", 0))[:depth_levels]

    total_bid = sum(l.get("size", 0.0) for l in bid_sizes)
    total_ask = sum(l.get("size", 0.0) for l in ask_sizes)
    denom = total_bid + total_ask
    if denom == 0:
        return 0.0
    return (total_bid - total_ask) / denom
