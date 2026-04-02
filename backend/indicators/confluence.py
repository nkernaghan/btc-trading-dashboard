"""Multi-timeframe confluence scoring — pure computation."""

from models.enums import VoteType


def calc_confluence(
    h1_direction: VoteType,
    h4_direction: VoteType,
    d1_direction: VoteType,
) -> tuple[int, int]:
    """Count aligned timeframes and compute bonus score.

    Returns (aligned_count, bonus_score):
        3 aligned → bonus +15
        2 aligned → bonus +5
        else      → bonus  0
    """
    directions = [h1_direction, h4_direction, d1_direction]

    # Count most common non-neutral direction
    bull_count = sum(1 for d in directions if d == VoteType.BULL)
    bear_count = sum(1 for d in directions if d == VoteType.BEAR)

    aligned = max(bull_count, bear_count)

    if aligned == 3:
        bonus = 15
    elif aligned == 2:
        bonus = 5
    else:
        bonus = 0

    return aligned, bonus
