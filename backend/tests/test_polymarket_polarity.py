"""Tests for data.sentiment._classify_polarity — Polymarket question framing.

Locks in the direction-keyword precedence, word-boundary matching, and
the known phrasing gaps (see follow-up #1 in the audit TODO).
"""

from data.sentiment import _classify_polarity


# ---- Directional keywords outrank action keywords ----

def test_crash_below_classifies_bear_via_direction():
    """'crash' is action-bear, 'below' is directional-bear — both agree on bear."""
    assert _classify_polarity("Will BTC crash below $50k by year-end?") == "bear"


def test_break_above_classifies_bull_via_direction():
    """'break' is action-bull, 'above' is directional-bull — both agree on bull."""
    assert _classify_polarity("Will BTC break above $120k in Q1?") == "bull"


def test_direction_bear_beats_action_bull():
    """Directional BEAR wins when mixed with an action-BULL keyword.

    The regression scenario: 'reach below' has action-bull ('reach') and
    directional-bear ('below'). Direction must win or we sign-flip the
    vote.
    """
    assert _classify_polarity("Will BTC reach below $40k?") == "bear"


def test_direction_bull_beats_action_bear():
    """Directional BULL wins when mixed with an action-BEAR keyword."""
    assert _classify_polarity("Will BTC fall above $80k support?") == "bull"


# ---- Common Polymarket phrasings (Codex-flagged) ----

def test_will_btc_reach_classifies_bull():
    """'Will BTC reach $X' — action-bull 'reach', no directional word."""
    assert _classify_polarity("Will BTC reach $150,000?") == "bull"


def test_will_btc_hit_ath_classifies_bull():
    """'Will BTC hit ATH' — action-bull 'hit' + 'ath' (two matches)."""
    assert _classify_polarity("Will BTC hit ATH in 2026?") == "bull"


def test_new_ath_classifies_bull():
    """Multi-word action-bull phrase ('new ath' / 'all-time high')."""
    assert _classify_polarity("Will BTC print a new ATH this year?") == "bull"
    assert _classify_polarity("Will BTC make a new all-time high?") == "bull"


def test_will_btc_crash_classifies_bear():
    """'Will BTC crash' — action-bear 'crash', no directional."""
    assert _classify_polarity("Will BTC crash to $30k?") == "bear"


def test_will_btc_plunge_classifies_bear():
    assert _classify_polarity("Will BTC plunge 20% this quarter?") == "bear"


# ---- Word-boundary matching (prevents silent substring mis-classification) ----

def test_recover_does_not_trigger_over():
    """'recover' contains 'over' but must NOT flip to bull-directional.

    Pre-regex implementations that substring-matched would mis-classify
    recovery-phrased questions.
    """
    # No directional, no action bull/bear → unknown
    assert _classify_polarity("Will BTC recover its losses?") == "unknown"


def test_weather_does_not_trigger_ath():
    """'weather' / 'cathedral' / 'death' all contain 'ath' as a substring
    but must NOT trigger the ATH action-bull keyword (regex is \\bath\\b).

    Using 'weather' here because phrases like 'death cross' would match
    the separate 'cross' action-bull keyword and invalidate the test.
    """
    assert _classify_polarity("Will weather disrupt BTC mining in Texas?") == "unknown"


def test_abandon_does_not_trigger_ban():
    """'abandon' contains 'ban' but must NOT trigger the ban action-bear."""
    assert _classify_polarity("Will miners abandon BTC after halving?") == "unknown"


# ---- Known gaps (follow-up #1) — lock in current behavior ----

def test_reserve_phrasing_is_unknown_known_gap():
    """'strategic reserve' / 'treasury' / 'buy' / 'reject' are not keywords
    today. Until the vocabulary is expanded (audit follow-up #1), these
    fall through to 'unknown' and consumers skip the vote — correct
    conservative behavior."""
    assert _classify_polarity("Will the US establish a strategic Bitcoin reserve?") == "unknown"


def test_treasury_phrasing_is_unknown_known_gap():
    assert _classify_polarity("Will MicroStrategy add BTC to its treasury?") == "unknown"


def test_buy_phrasing_is_unknown_known_gap():
    assert _classify_polarity("Will Saylor buy more BTC this month?") == "unknown"


def test_reject_phrasing_is_unknown_known_gap():
    """'reject' reads as bearish to a human but isn't in the action-bear
    list today."""
    assert _classify_polarity("Will the SEC reject the next spot ETF?") == "unknown"


# ---- Edge cases ----

def test_empty_question_is_unknown():
    assert _classify_polarity("") == "unknown"


def test_no_keywords_is_unknown():
    assert _classify_polarity("Will there be an event at Consensus?") == "unknown"


def test_case_insensitive():
    """Case should not matter for any keyword."""
    assert _classify_polarity("WILL BTC REACH $200,000?") == "bull"
    assert _classify_polarity("will btc CRASH below $30k") == "bear"
