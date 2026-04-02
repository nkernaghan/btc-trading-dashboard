"""Market-structure detection — pure computation, no I/O."""

import numpy as np


def detect_swing_points(
    highs: np.ndarray, lows: np.ndarray, lookback: int = 2
) -> tuple[list[float], list[float]]:
    """Detect swing highs and swing lows.

    A swing high at index i means highs[i] is the max in [i-lookback, i+lookback].
    Returns (swing_highs, swing_lows) as lists of price values.
    """
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    n = len(highs)

    for i in range(lookback, n - lookback):
        # Swing high
        is_high = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_high = False
                break
        if is_high:
            swing_highs.append(float(highs[i]))

        # Swing low
        is_low = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_low = False
                break
        if is_low:
            swing_lows.append(float(lows[i]))

    return swing_highs, swing_lows


def detect_bos_choch(
    swing_highs: list[float], swing_lows: list[float]
) -> dict:
    """Detect Break of Structure (BOS) or Change of Character (CHoCH).

    Returns {"structure": "bullish"|"bearish"|"neutral", "event": "BOS"|"CHoCH"|None}
    """
    result: dict = {"structure": "neutral", "event": None}
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return result

    hh = swing_highs[-1] > swing_highs[-2]  # higher high
    hl = swing_lows[-1] > swing_lows[-2]     # higher low
    lh = swing_highs[-1] < swing_highs[-2]   # lower high
    ll = swing_lows[-1] < swing_lows[-2]     # lower low

    if hh and hl:
        # Bullish structure — BOS if continuing, CHoCH if reversing from bearish
        result["structure"] = "bullish"
        result["event"] = "BOS"
    elif ll and lh:
        # Bearish structure
        result["structure"] = "bearish"
        result["event"] = "BOS"
    elif hh and ll:
        # Mixed — change of character
        result["structure"] = "bullish"
        result["event"] = "CHoCH"
    elif lh and hl:
        result["structure"] = "bearish"
        result["event"] = "CHoCH"
    else:
        # Partial signals
        if hh or hl:
            result["structure"] = "bullish"
            result["event"] = "BOS"
        elif lh or ll:
            result["structure"] = "bearish"
            result["event"] = "BOS"

    return result


def detect_order_blocks(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> list[dict]:
    """Detect last 5 order blocks (significant candles before strong moves).

    An order block is the last opposing candle before an impulsive move.
    Returns list of {"type": "bullish"|"bearish", "high": float, "low": float, "index": int}
    """
    obs: list[dict] = []
    n = len(closes)
    if n < 3:
        return obs

    for i in range(1, n - 1):
        body_curr = closes[i] - opens[i]
        body_next = closes[i + 1] - opens[i + 1]

        # Bullish OB: bearish candle followed by strong bullish candle
        if body_curr < 0 and body_next > 0 and abs(body_next) > abs(body_curr) * 1.5:
            obs.append({
                "type": "bullish",
                "high": float(highs[i]),
                "low": float(lows[i]),
                "index": i,
            })
        # Bearish OB: bullish candle followed by strong bearish candle
        elif body_curr > 0 and body_next < 0 and abs(body_next) > abs(body_curr) * 1.5:
            obs.append({
                "type": "bearish",
                "high": float(highs[i]),
                "low": float(lows[i]),
                "index": i,
            })

    return obs[-5:]


def detect_fair_value_gaps(
    highs: np.ndarray, lows: np.ndarray
) -> list[dict]:
    """Detect last 5 Fair Value Gaps (FVGs).

    Bullish FVG: low[i+1] > high[i-1]  (gap up)
    Bearish FVG: high[i+1] < low[i-1]  (gap down)
    Returns list of {"type": "bullish"|"bearish", "top": float, "bottom": float, "index": int}
    """
    fvgs: list[dict] = []
    n = len(highs)
    if n < 3:
        return fvgs

    for i in range(1, n - 1):
        # Bullish FVG — gap between candle i-1 high and candle i+1 low
        if lows[i + 1] > highs[i - 1]:
            fvgs.append({
                "type": "bullish",
                "top": float(lows[i + 1]),
                "bottom": float(highs[i - 1]),
                "index": i,
            })
        # Bearish FVG — gap between candle i-1 low and candle i+1 high
        elif highs[i + 1] < lows[i - 1]:
            fvgs.append({
                "type": "bearish",
                "top": float(lows[i - 1]),
                "bottom": float(highs[i + 1]),
                "index": i,
            })

    return fvgs[-5:]


def detect_cme_gaps(
    daily_closes: list[dict], current_price: float
) -> list[dict]:
    """Detect unfilled CME gaps (weekend gaps).

    Each daily_close dict: {"date": str, "close": float, "open": float}
    Returns list of {"low": float, "high": float, "date": str, "direction": "up"|"down", "filled": bool}
    """
    gaps: list[dict] = []
    if len(daily_closes) < 2:
        return gaps

    for i in range(1, len(daily_closes)):
        prev_close = daily_closes[i - 1]["close"]
        curr_open = daily_closes[i]["open"]

        # Gap up: current open above previous close
        if curr_open > prev_close * 1.001:  # >0.1% gap threshold
            gap_low = prev_close
            gap_high = curr_open
            filled = current_price <= gap_low
            gaps.append({
                "low": gap_low,
                "high": gap_high,
                "date": daily_closes[i]["date"],
                "direction": "up",
                "filled": filled,
            })
        # Gap down: current open below previous close
        elif curr_open < prev_close * 0.999:
            gap_low = curr_open
            gap_high = prev_close
            filled = current_price >= gap_high
            gaps.append({
                "low": gap_low,
                "high": gap_high,
                "date": daily_closes[i]["date"],
                "direction": "down",
                "filled": filled,
            })

    return gaps
