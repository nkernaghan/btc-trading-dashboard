import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.schemas import IndicatorVote
from models.enums import IndicatorCategory, VoteType, Direction, SignalStrength
from scoring.vote_aggregator import aggregate_category_score, compute_weighted_score
from scoring.composite import compute_composite_signal


def make_vote(name, category, vote, strength=2, value=0):
    return IndicatorVote(
        name=name,
        category=category,
        vote=vote,
        strength=strength,
        value=value,
        description=f"{name}: {value}",
    )


def test_all_bullish_scores_high():
    """All BULL votes with strength 3 should produce a score > 90."""
    votes = [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("OF2", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=3),
        make_vote("MD2", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=3),
        make_vote("OC1", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=3),
        make_vote("OC2", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=3),
        make_vote("S1", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=3),
        make_vote("S2", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=3),
    ]
    score = compute_weighted_score(votes)
    assert score > 90, f"Expected score > 90, got {score}"


def test_all_bearish_scores_low():
    """All BEAR votes with strength 3 should produce a score < 10."""
    votes = [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BEAR, strength=3),
        make_vote("OF2", IndicatorCategory.ORDER_FLOW, VoteType.BEAR, strength=3),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BEAR, strength=3),
        make_vote("MD2", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BEAR, strength=3),
        make_vote("OC1", IndicatorCategory.ON_CHAIN, VoteType.BEAR, strength=3),
        make_vote("OC2", IndicatorCategory.ON_CHAIN, VoteType.BEAR, strength=3),
        make_vote("S1", IndicatorCategory.SENTIMENT, VoteType.BEAR, strength=3),
        make_vote("S2", IndicatorCategory.SENTIMENT, VoteType.BEAR, strength=3),
    ]
    score = compute_weighted_score(votes)
    assert score < 10, f"Expected score < 10, got {score}"


def test_mixed_scores_neutral():
    """Mixed BULL/BEAR/NEUTRAL votes should produce a score between 30-70."""
    votes = [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=2),
        make_vote("OF2", IndicatorCategory.ORDER_FLOW, VoteType.BEAR, strength=1),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.NEUTRAL, strength=2),
        make_vote("MD2", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=1),
        make_vote("OC1", IndicatorCategory.ON_CHAIN, VoteType.BEAR, strength=2),
        make_vote("OC2", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=2),
        make_vote("S1", IndicatorCategory.SENTIMENT, VoteType.NEUTRAL, strength=1),
        make_vote("S2", IndicatorCategory.SENTIMENT, VoteType.BEAR, strength=1),
    ]
    score = compute_weighted_score(votes)
    assert 30 <= score <= 70, f"Expected score between 30-70, got {score}"


def test_composite_signal_long():
    """Mostly bullish + confluence 3 + rsi 55 + ema_aligned -> LONG, score > 70."""
    votes = [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("OF2", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=3),
        make_vote("MD2", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=2),
        make_vote("OC1", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=3),
        make_vote("OC2", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=2),
        make_vote("S1", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=3),
        make_vote("S2", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=2),
    ]
    result = compute_composite_signal(
        votes=votes,
        confluence_count=3,
        confluence_bonus=5,
        rsi=55.0,
        ema_aligned=True,
    )
    assert result["direction"] == Direction.LONG, f"Expected LONG, got {result['direction']}"
    assert result["score"] > 70, f"Expected score > 70, got {result['score']}"
    assert result["strength"] == SignalStrength.STRONG


def test_composite_signal_blocked_by_rsi():
    """All bullish BUT rsi=85 should produce WAIT due to RSI overbought gate."""
    votes = [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("OF2", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=3),
        make_vote("MD2", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=3),
        make_vote("OC1", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=3),
        make_vote("OC2", IndicatorCategory.ON_CHAIN, VoteType.BULL, strength=3),
        make_vote("S1", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=3),
        make_vote("S2", IndicatorCategory.SENTIMENT, VoteType.BULL, strength=3),
    ]
    result = compute_composite_signal(
        votes=votes,
        confluence_count=4,
        confluence_bonus=5,
        rsi=85.0,
        ema_aligned=True,
    )
    assert result["direction"] == Direction.WAIT, f"Expected WAIT, got {result['direction']}"
    assert result["score"] <= 49, f"Expected score <= 49, got {result['score']}"
