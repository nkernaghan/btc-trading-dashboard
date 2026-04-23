"""High-level technical analysis — computes RSI, EMA alignment, market structure,
ATR, and volatility regime from OHLCV arrays.

Wraps the pure indicator functions in indicators/technical.py,
indicators/market_structure.py, and indicators/volatility.py.
"""

import numpy as np

from indicators.technical import calc_rsi, calc_ema, calc_atr, calc_macd
from indicators.market_structure import detect_swing_points, detect_bos_choch
from indicators.volatility import calc_rolling_realized_vol, calc_vol_regime


def compute_technical_snapshot(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> dict:
    """Compute a full technical snapshot from OHLCV arrays.

    Returns dict with:
        rsi: float (0-100)
        ema_aligned: bool (True if EMA21 > EMA55 > EMA200 or reverse)
        structure: str ("bullish", "bearish", "neutral")
        atr: float
        vol_regime: str ("low", "normal", "high", "extreme")
        macd_histogram: float
        ema_21: float
        ema_55: float
        ema_200: float
    """
    n = len(closes)

    if n < 15:
        return {
            "rsi": 50.0,
            "ema_aligned": True,
            "structure": "neutral",
            "atr": float(np.mean(highs - lows)) if n > 0 else 0.0,
            "vol_regime": "normal",
            "macd_histogram": 0.0,
            "ema_21": float(closes[-1]) if n > 0 else 0.0,
            "ema_55": float(closes[-1]) if n > 0 else 0.0,
            "ema_200": float(closes[-1]) if n > 0 else 0.0,
        }

    # RSI
    rsi = calc_rsi(closes, period=14)

    # EMAs
    ema_21 = calc_ema(closes, 21)
    ema_55 = calc_ema(closes, 55)
    ema_200 = calc_ema(closes, 200)

    # EMA alignment: bullish if 21 > 55 > 200, bearish if 21 < 55 < 200
    bullish_aligned = ema_21 > ema_55 > ema_200
    bearish_aligned = ema_21 < ema_55 < ema_200
    ema_aligned = bullish_aligned or bearish_aligned

    # MACD
    _, _, macd_hist = calc_macd(closes)

    # ATR
    atr = calc_atr(highs, lows, closes, period=14)

    # Market structure from swing points
    swing_highs, swing_lows = detect_swing_points(highs, lows, lookback=2)
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        bos_result = detect_bos_choch(swing_highs, swing_lows)
        structure = bos_result["structure"]
    else:
        structure = "neutral"

    # Volatility regime
    if n >= 24:
        current_vol = calc_rolling_realized_vol(closes, window=24)
        vol_history = []
        for i in range(24, n):
            vol_history.append(calc_rolling_realized_vol(closes[:i + 1], window=24))
        vol_regime = calc_vol_regime(current_vol, vol_history) if vol_history else "normal"
    else:
        vol_regime = "normal"

    return {
        "rsi": rsi,
        "ema_aligned": ema_aligned,
        "structure": structure,
        "atr": atr,
        "vol_regime": vol_regime,
        "macd_histogram": macd_hist,
        "ema_21": ema_21,
        "ema_55": ema_55,
        "ema_200": ema_200,
    }
