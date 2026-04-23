from models.schemas import IndicatorVote
from models.enums import Direction, SignalStrength
from scoring.vote_aggregator import compute_weighted_score
from scoring.technical_gate import apply_technical_gate


def compute_composite_signal(
    votes: list[IndicatorVote],
    confluence_count: int,
    confluence_bonus: int,
    rsi: float,
    ema_aligned: bool,
) -> dict:
    """Compute final composite signal.

    Steps:
    1. Get weighted score from vote aggregator
    2. Add confluence bonus (cap at 100)
    3. Determine raw direction (>=50 = LONG, <50 = SHORT; flip score for shorts)
    4. Apply technical gate (RSI + EMA; structure is voted on, not gated)
    5. Classify strength: >=70 STRONG, >=50 WEAK, <50 NONE (-> WAIT)

    Returns dict with direction, score, strength, raw_score, confluence_count.
    """
    # Step 1: weighted score
    raw_score = compute_weighted_score(votes)

    # Step 2: add confluence bonus
    boosted_score = min(100.0, raw_score + confluence_bonus)

    # Step 3: determine direction
    if boosted_score >= 50:
        direction = Direction.LONG
        directional_score = boosted_score
    else:
        direction = Direction.SHORT
        # Flip score so that lower raw = higher short confidence
        # e.g. raw 20 -> short confidence 80
        directional_score = 100.0 - boosted_score

    # Step 4: apply technical gate
    final_direction, final_score = apply_technical_gate(
        direction, directional_score, rsi, ema_aligned
    )

    # Step 5: classify strength
    if final_score >= 70:
        strength = SignalStrength.STRONG
    elif final_score >= 50:
        strength = SignalStrength.WEAK
    else:
        strength = SignalStrength.NONE
        final_direction = Direction.WAIT

    return {
        "direction": final_direction,
        "score": final_score,
        "strength": strength,
        "raw_score": raw_score,
        "confluence_count": confluence_count,
    }
