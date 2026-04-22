import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.schemas import IndicatorVote
from models.enums import Direction, SignalStrength, IndicatorCategory, VoteType
from scoring.signal_generator import generate_signal


def make_vote(name, category, vote, strength=2, value=0):
    return IndicatorVote(
        name=name,
        category=category,
        vote=vote,
        strength=strength,
        value=value,
        description=f"{name}: {value}",
    )


def _sample_votes():
    return [
        make_vote("OF1", IndicatorCategory.ORDER_FLOW, VoteType.BULL, strength=3),
        make_vote("MD1", IndicatorCategory.MACRO_DERIVATIVES, VoteType.BULL, strength=2),
    ]


def test_generate_long_signal():
    """LONG direction should produce valid entry, SL, TP, leverage, liq, and R:R."""
    sig = generate_signal(
        direction=Direction.LONG,
        score=75.0,
        current_price=65000.0,
        atr=500.0,
        vol_regime="normal",
        confluence_count=3,
        votes=_sample_votes(),
        warnings=[],
    )
    assert sig.direction == Direction.LONG
    assert sig.entry_low < sig.entry_high
    assert sig.stop_loss < sig.entry_low, "SL should be below entry for LONG"
    assert sig.take_profit_1 > sig.entry_high, "TP1 should be above entry for LONG"
    assert sig.take_profit_2 > sig.take_profit_1, "TP2 should be above TP1"
    assert 20 <= sig.recommended_leverage <= 30, f"Expected leverage 20-30, got {sig.recommended_leverage}"
    assert sig.liquidation_price < sig.stop_loss, "Liq should be below SL for LONG"
    assert sig.risk_reward_ratio > 1, f"Expected R:R > 1, got {sig.risk_reward_ratio}"


def test_generate_short_signal():
    """SHORT direction should produce SL above entry, TP below entry, liq above SL."""
    sig = generate_signal(
        direction=Direction.SHORT,
        score=80.0,
        current_price=65000.0,
        atr=500.0,
        vol_regime="normal",
        confluence_count=2,
        votes=_sample_votes(),
        warnings=[],
    )
    assert sig.direction == Direction.SHORT
    assert sig.stop_loss > sig.entry_high, "SL should be above entry for SHORT"
    assert sig.take_profit_1 < sig.entry_low, "TP1 should be below entry for SHORT"
    assert sig.liquidation_price > sig.stop_loss, "Liq should be above SL for SHORT"


def test_leverage_reduced_in_high_vol():
    """vol_regime='high' should produce leverage <= 15."""
    sig = generate_signal(
        direction=Direction.LONG,
        score=75.0,
        current_price=65000.0,
        atr=800.0,
        vol_regime="high",
        confluence_count=2,
        votes=_sample_votes(),
        warnings=[],
    )
    assert sig.recommended_leverage <= 15, f"Expected leverage <= 15, got {sig.recommended_leverage}"


def test_wait_signal():
    """WAIT direction should produce zero leverage and zero prices."""
    sig = generate_signal(
        direction=Direction.WAIT,
        score=40.0,
        current_price=65000.0,
        atr=500.0,
        vol_regime="normal",
        confluence_count=0,
        votes=_sample_votes(),
        warnings=["RSI overbought"],
    )
    assert sig.direction == Direction.WAIT
    assert sig.recommended_leverage == 0
    assert sig.entry_low == 0.0
    assert sig.entry_high == 0.0
    assert sig.stop_loss == 0.0
    assert sig.take_profit_1 == 0.0
    assert sig.take_profit_2 == 0.0
    assert sig.liquidation_price == 0.0
