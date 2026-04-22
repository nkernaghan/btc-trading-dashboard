from models.enums import Direction


def apply_technical_gate(
    direction: Direction,
    composite_score: float,
    rsi: float,
    ema_aligned: bool,
    structure: str,
) -> tuple[Direction, float]:
    """Apply technical filters that can block or weaken a signal.

    Filters:
    - RSI > 80 blocks LONG -> WAIT, cap score at 49
    - RSI < 20 blocks SHORT -> WAIT, cap score at 49
    - No EMA alignment -> score *= 0.8
    - Structure opposes signal -> WAIT, cap score at 49

    Returns adjusted (direction, score).
    """
    adj_direction = direction
    adj_score = composite_score

    # RSI overbought blocks longs
    if direction == Direction.LONG and rsi > 80:
        adj_direction = Direction.WAIT
        adj_score = min(adj_score, 49.0)
        return adj_direction, adj_score

    # RSI oversold blocks shorts
    if direction == Direction.SHORT and rsi < 20:
        adj_direction = Direction.WAIT
        adj_score = min(adj_score, 49.0)
        return adj_direction, adj_score

    # EMA misalignment weakens signal
    if not ema_aligned:
        adj_score *= 0.8

    # Structure opposition blocks signal
    if direction == Direction.LONG and structure == "bearish":
        adj_direction = Direction.WAIT
        adj_score = min(adj_score, 49.0)
    elif direction == Direction.SHORT and structure == "bullish":
        adj_direction = Direction.WAIT
        adj_score = min(adj_score, 49.0)

    return adj_direction, adj_score
