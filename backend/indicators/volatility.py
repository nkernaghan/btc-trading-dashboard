"""Volatility indicators — pure computation, no I/O."""

import numpy as np


def calc_garch_forecast(returns: np.ndarray, horizon: int = 1) -> float:
    """GARCH(1,1) annualized volatility forecast.

    Tries the `arch` library first; falls back to simple rolling std.
    """
    if len(returns) < 10:
        return float(np.std(returns) * np.sqrt(365))

    try:
        from arch import arch_model

        # Scale returns to percentage for numerical stability
        scaled = returns * 100.0
        model = arch_model(scaled, vol="Garch", p=1, q=1, rescale=False)
        result = model.fit(disp="off", show_warning=False)
        forecast = result.forecast(horizon=horizon)
        # variance is in pct^2, convert back
        var_pct = float(forecast.variance.values[-1, 0])
        daily_vol = np.sqrt(var_pct) / 100.0
        return float(daily_vol * np.sqrt(365))
    except Exception:
        # Fallback: simple annualized std of returns
        daily_vol = float(np.std(returns))
        return float(daily_vol * np.sqrt(365))


def calc_rolling_realized_vol(prices: np.ndarray, window: int = 24) -> float:
    """Rolling realized volatility from log returns over `window` periods."""
    if len(prices) < 2:
        return 0.0
    log_returns = np.diff(np.log(prices))
    w = min(window, len(log_returns))
    recent = log_returns[-w:]
    return float(np.std(recent) * np.sqrt(w))


def calc_vol_regime(current_vol: float, vol_history: list[float]) -> str:
    """Classify volatility regime based on percentile rank.

    Returns "low" / "normal" / "high" / "extreme" using 25/75/90 thresholds.
    """
    if not vol_history:
        return "normal"
    arr = np.array(vol_history)
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    p90 = float(np.percentile(arr, 90))

    if current_vol <= p25:
        return "low"
    elif current_vol <= p75:
        return "normal"
    elif current_vol <= p90:
        return "high"
    else:
        return "extreme"
