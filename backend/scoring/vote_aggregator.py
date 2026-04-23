from models.schemas import IndicatorVote
from models.enums import IndicatorCategory, VoteType

CATEGORY_WEIGHTS = {
    IndicatorCategory.ORDER_FLOW: 0.20,
    IndicatorCategory.MACRO_DERIVATIVES: 0.15,
    IndicatorCategory.ON_CHAIN: 0.10,
    IndicatorCategory.SENTIMENT: 0.10,
    IndicatorCategory.TECHNICAL: 0.30,
    IndicatorCategory.GEOPOLITICAL: 0.15,
}

MAX_STRENGTH = 3


def aggregate_category_score(
    votes: list[IndicatorVote], category: IndicatorCategory
) -> float:
    """Aggregate votes in a category to a 0-100 score.

    BULL -> +strength, BEAR -> -strength, NEUTRAL -> 0.
    Normalize from [-max_possible, +max_possible] to [0, 100].
    """
    cat_votes = [v for v in votes if v.category == category]
    if not cat_votes:
        return 50.0

    raw_sum = 0.0
    max_possible = 0.0
    for v in cat_votes:
        max_possible += MAX_STRENGTH
        if v.vote == VoteType.BULL:
            raw_sum += v.strength
        elif v.vote == VoteType.BEAR:
            raw_sum -= v.strength
        # NEUTRAL and WARN contribute 0

    if max_possible == 0:
        return 50.0

    # Normalize from [-max_possible, +max_possible] to [0, 100]
    normalized = (raw_sum + max_possible) / (2 * max_possible) * 100
    return max(0.0, min(100.0, normalized))


def compute_weighted_score(votes: list[IndicatorVote]) -> float:
    """Weighted composite score across all categories. Returns 0-100."""
    total_weight = 0.0
    weighted_sum = 0.0

    for category, weight in CATEGORY_WEIGHTS.items():
        cat_votes = [v for v in votes if v.category == category]
        if cat_votes:
            score = aggregate_category_score(votes, category)
            weighted_sum += score * weight
            total_weight += weight

    if total_weight == 0:
        return 50.0

    return max(0.0, min(100.0, weighted_sum / total_weight))
