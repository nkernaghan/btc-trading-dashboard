"""Technical indicators — pure numpy computation, no I/O."""

import numpy as np


def calc_ema(prices: np.ndarray, period: int) -> float:
    """Exponential Moving Average. Returns the last EMA value."""
    if len(prices) < period:
        return float(prices[-1])
    multiplier = 2.0 / (period + 1)
    ema = float(prices[0])
    for price in prices[1:]:
        ema = (float(price) - ema) * multiplier + ema
    return ema


def calc_rsi(prices: np.ndarray, period: int = 14) -> float:
    """RSI (0-100) using Wilder's smoothing method."""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices).astype(float)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Initial averages over the first `period` changes
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Wilder's smoothing for subsequent values
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_macd(
    prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float, float, float]:
    """MACD line, signal line, histogram."""
    fast_ema = _ema_series(prices, fast)
    slow_ema = _ema_series(prices, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _ema_series(macd_line, signal)
    histogram = macd_line - signal_line
    return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])


def calc_bollinger_bands(
    prices: np.ndarray, period: int = 20, std_dev: float = 2.0
) -> tuple[float, float, float]:
    """Upper, middle, lower Bollinger Bands."""
    if len(prices) < period:
        mid = float(np.mean(prices))
        sd = float(np.std(prices))
        return mid + std_dev * sd, mid, mid - std_dev * sd
    window = prices[-period:]
    mid = float(np.mean(window))
    sd = float(np.std(window))
    return mid + std_dev * sd, mid, mid - std_dev * sd


def calc_atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
) -> float:
    """Average True Range using Wilder's smoothing."""
    if len(closes) < 2:
        return float(highs[0] - lows[0])
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ),
    )
    if len(tr) < period:
        return float(np.mean(tr))
    atr = float(np.mean(tr[:period]))
    for i in range(period, len(tr)):
        atr = (atr * (period - 1) + float(tr[i])) / period
    return atr


def calc_stoch_rsi(
    prices: np.ndarray, period: int = 14, smooth_k: int = 3, smooth_d: int = 3
) -> tuple[float, float]:
    """%K and %D of Stochastic RSI (0-100)."""
    if len(prices) < period + smooth_k + smooth_d + 1:
        return 50.0, 50.0

    # Build RSI series
    deltas = np.diff(prices).astype(float)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    rsi_series = []
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        rsi_series.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_series.append(100.0 - 100.0 / (1.0 + rs))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_series.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_series.append(100.0 - 100.0 / (1.0 + rs))

    rsi_arr = np.array(rsi_series)
    if len(rsi_arr) < period:
        return 50.0, 50.0

    # Stochastic of RSI
    stoch_rsi = []
    for i in range(period - 1, len(rsi_arr)):
        window = rsi_arr[i - period + 1 : i + 1]
        lo, hi = np.min(window), np.max(window)
        if hi == lo:
            stoch_rsi.append(50.0)
        else:
            stoch_rsi.append((rsi_arr[i] - lo) / (hi - lo) * 100.0)

    stoch_rsi = np.array(stoch_rsi)
    if len(stoch_rsi) < smooth_k:
        k = float(stoch_rsi[-1]) if len(stoch_rsi) > 0 else 50.0
        return k, k

    # %K = SMA of stoch_rsi
    k_series = np.convolve(stoch_rsi, np.ones(smooth_k) / smooth_k, mode="valid")
    if len(k_series) < smooth_d:
        return float(k_series[-1]), float(k_series[-1])

    # %D = SMA of %K
    d_series = np.convolve(k_series, np.ones(smooth_d) / smooth_d, mode="valid")
    return float(np.clip(k_series[-1], 0, 100)), float(np.clip(d_series[-1], 0, 100))


def calc_williams_r(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
) -> float:
    """Williams %R (-100 to 0)."""
    if len(closes) < period:
        period = len(closes)
    highest = float(np.max(highs[-period:]))
    lowest = float(np.min(lows[-period:]))
    if highest == lowest:
        return -50.0
    return -100.0 * (highest - float(closes[-1])) / (highest - lowest)


def calc_vwap(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray
) -> float:
    """Volume Weighted Average Price."""
    typical = (highs + lows + closes) / 3.0
    total_vol = np.sum(volumes)
    if total_vol == 0:
        return float(np.mean(typical))
    return float(np.sum(typical * volumes) / total_vol)


def calc_keltner_channels(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 20,
    atr_mult: float = 1.5,
) -> tuple[float, float, float]:
    """Upper, middle, lower Keltner Channels."""
    middle = calc_ema(closes, period)
    atr = calc_atr(highs, lows, closes, period)
    return middle + atr_mult * atr, middle, middle - atr_mult * atr


def calc_ichimoku(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    tenkan: int = 9,
    kijun: int = 26,
    senkou_b: int = 52,
) -> tuple[float, float, float, float, float]:
    """Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, Chikou Span."""
    def midline(arr: np.ndarray, period: int) -> float:
        if len(arr) < period:
            period = len(arr)
        return float((np.max(arr[-period:]) + np.min(arr[-period:])) / 2.0)

    tenkan_val = (midline(highs, tenkan) + midline(lows, tenkan)) / 2.0
    # Actually: tenkan = (highest_high + lowest_low) / 2 over tenkan period
    t = tenkan if len(highs) >= tenkan else len(highs)
    tenkan_val = float((np.max(highs[-t:]) + np.min(lows[-t:])) / 2.0)

    k = kijun if len(highs) >= kijun else len(highs)
    kijun_val = float((np.max(highs[-k:]) + np.min(lows[-k:])) / 2.0)

    senkou_a_val = (tenkan_val + kijun_val) / 2.0

    sb = senkou_b if len(highs) >= senkou_b else len(highs)
    senkou_b_val = float((np.max(highs[-sb:]) + np.min(lows[-sb:])) / 2.0)

    chikou_val = float(closes[-1])

    return tenkan_val, kijun_val, senkou_a_val, senkou_b_val, chikou_val


# ── helpers ──────────────────────────────────────────────────────────────

def _ema_series(data: np.ndarray, period: int) -> np.ndarray:
    """Return full EMA series as ndarray."""
    out = np.empty_like(data, dtype=float)
    multiplier = 2.0 / (period + 1)
    out[0] = float(data[0])
    for i in range(1, len(data)):
        out[i] = (float(data[i]) - out[i - 1]) * multiplier + out[i - 1]
    return out
