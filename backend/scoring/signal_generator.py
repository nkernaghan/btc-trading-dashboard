from datetime import datetime, timezone
from models.schemas import Signal, IndicatorVote
from models.enums import Direction, SignalStrength

LEVERAGE_BY_REGIME = {
    "low": (30, 40),
    "normal": (20, 30),
    "high": (10, 15),
    "extreme": (0, 5),
}


def generate_signal(
    direction: Direction,
    score: float,
    current_price: float,
    atr: float,
    vol_regime: str,
    confluence_count: int,
    votes: list[IndicatorVote],
    warnings: list[str],
) -> Signal:
    """Generate a complete trading signal.

    - WAIT or score < 50 produces a zero-value Signal with WAIT direction.
    - Leverage derived from vol_regime range scaled by confidence factor.
    - Entry zone: price +/- 0.15%.
    - Stop loss: 1.5x ATR from entry.
    - TP1: 2.5x ATR from entry, TP2: 4.0x ATR from entry.
    - Liquidation price: entry * (1 - 1/leverage) for LONG,
      entry * (1 + 1/leverage) for SHORT.
    - Risk/reward = TP1 distance / SL distance.
    """
    now = datetime.now(timezone.utc)

    # WAIT or low score -> zero signal
    if direction == Direction.WAIT or score < 50:
        return Signal(
            timestamp=now,
            direction=Direction.WAIT,
            composite_score=score,
            strength=SignalStrength.NONE,
            entry_low=0.0,
            entry_high=0.0,
            stop_loss=0.0,
            stop_loss_pct=0.0,
            take_profit_1=0.0,
            take_profit_1_pct=0.0,
            take_profit_2=0.0,
            take_profit_2_pct=0.0,
            recommended_leverage=0,
            liquidation_price=0.0,
            risk_reward_ratio=0.0,
            confluence_count=confluence_count,
            votes=votes,
            warnings=warnings,
        )

    # Determine leverage from volatility regime
    lev_min, lev_max = LEVERAGE_BY_REGIME.get(vol_regime, (20, 30))
    confidence_factor = (score - 50) / 50  # 0.0 to 1.0
    leverage = int(lev_min + (lev_max - lev_min) * confidence_factor)
    leverage = max(1, leverage)  # ensure at least 1x

    # Strength classification
    if score >= 70:
        strength = SignalStrength.STRONG
    elif score >= 50:
        strength = SignalStrength.WEAK
    else:
        strength = SignalStrength.NONE

    # Entry zone
    entry_offset = current_price * 0.0015
    if direction == Direction.LONG:
        entry_low = current_price - entry_offset
        entry_high = current_price + entry_offset
        entry_mid = current_price

        # Stop loss below entry
        stop_loss = entry_mid - 1.5 * atr
        stop_loss_pct = abs(entry_mid - stop_loss) / entry_mid * 100

        # Take profits above entry
        take_profit_1 = entry_mid + 2.5 * atr
        take_profit_1_pct = abs(take_profit_1 - entry_mid) / entry_mid * 100
        take_profit_2 = entry_mid + 4.0 * atr
        take_profit_2_pct = abs(take_profit_2 - entry_mid) / entry_mid * 100

        # Liquidation price for long
        liquidation_price = entry_mid * (1 - 1 / leverage)

    else:  # SHORT
        entry_high = current_price + entry_offset
        entry_low = current_price - entry_offset
        entry_mid = current_price

        # Stop loss above entry
        stop_loss = entry_mid + 1.5 * atr
        stop_loss_pct = abs(stop_loss - entry_mid) / entry_mid * 100

        # Take profits below entry
        take_profit_1 = entry_mid - 2.5 * atr
        take_profit_1_pct = abs(entry_mid - take_profit_1) / entry_mid * 100
        take_profit_2 = entry_mid - 4.0 * atr
        take_profit_2_pct = abs(entry_mid - take_profit_2) / entry_mid * 100

        # Liquidation price for short
        liquidation_price = entry_mid * (1 + 1 / leverage)

    # Risk/reward ratio
    sl_distance = abs(entry_mid - stop_loss)
    tp1_distance = abs(take_profit_1 - entry_mid)
    risk_reward_ratio = tp1_distance / sl_distance if sl_distance > 0 else 0.0

    return Signal(
        timestamp=now,
        direction=direction,
        composite_score=score,
        strength=strength,
        entry_low=round(entry_low, 2),
        entry_high=round(entry_high, 2),
        stop_loss=round(stop_loss, 2),
        stop_loss_pct=round(stop_loss_pct, 4),
        take_profit_1=round(take_profit_1, 2),
        take_profit_1_pct=round(take_profit_1_pct, 4),
        take_profit_2=round(take_profit_2, 2),
        take_profit_2_pct=round(take_profit_2_pct, 4),
        recommended_leverage=leverage,
        liquidation_price=round(liquidation_price, 2),
        risk_reward_ratio=round(risk_reward_ratio, 2),
        confluence_count=confluence_count,
        votes=votes,
        warnings=warnings,
    )
