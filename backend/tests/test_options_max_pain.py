"""Tests for data.options — Deribit expiry parsing and real max-pain math."""

from datetime import datetime, timezone

import pytest

from data.options import _parse_deribit_expiry, _compute_max_pain


# ── _parse_deribit_expiry ────────────────────────────────────────────

def test_parse_deribit_expiry_uppercase_month():
    dt = _parse_deribit_expiry("28JUN24")
    assert dt == datetime(2024, 6, 28, 8, 0, 0, tzinfo=timezone.utc)


def test_parse_deribit_expiry_rejects_bad_month():
    assert _parse_deribit_expiry("28XYZ24") is None


def test_parse_deribit_expiry_rejects_short_string():
    assert _parse_deribit_expiry("28J") is None


def test_parse_deribit_expiry_rejects_empty():
    assert _parse_deribit_expiry("") is None
    assert _parse_deribit_expiry(None) is None  # type: ignore[arg-type]


def test_parse_deribit_expiry_mixed_case():
    """Case-insensitive month parsing — Deribit happens to use UPPER
    but we accept any case for robustness."""
    dt = _parse_deribit_expiry("01Jan30")
    assert dt == datetime(2030, 1, 1, 8, 0, 0, tzinfo=timezone.utc)


# ── _compute_max_pain ────────────────────────────────────────────────

def test_compute_max_pain_empty():
    assert _compute_max_pain([]) == 0.0


def test_compute_max_pain_single_call_writer_wants_price_at_or_below_strike():
    """One call at strike 100 with 10 OI. Writer payout is 0 at any S<=100
    and increasing above. Min is anywhere <=100; the minimum strike in
    the set is 100 itself (call's own strike), and payout_at(100)=0."""
    contracts = [(100.0, 10.0, True)]
    assert _compute_max_pain(contracts) == 100.0


def test_compute_max_pain_single_put_writer_wants_price_at_or_above_strike():
    """One put at strike 100. Writer payout is 0 at S>=100, positive below.
    Min is at the strike itself (only strike in the candidate set)."""
    contracts = [(100.0, 10.0, False)]
    assert _compute_max_pain(contracts) == 100.0


def test_compute_max_pain_skewed_call_put_mix():
    """Asymmetric OI: heavy calls at 120, light puts at 80.
    Payouts:
      S=80: call writers pay 0, put writers pay 0 -> total 0
      S=120: call writers pay 0, put writers pay (120-80)*5=200
    Answer: 80 (lower strike kills call payout at expense of tiny put).
    Actually at S=80: call payout = max(80-120,0)*20 = 0; put payout =
    max(80-80,0)*5 = 0. Total 0. At S=120: call payout = 0, put payout
    = (120-80)*5 = 200. So the answer is indeed 80."""
    contracts = [
        (120.0, 20.0, True),   # call OI 20 at 120
        (80.0, 5.0, False),    # put OI 5 at 80
    ]
    assert _compute_max_pain(contracts) == 80.0


def test_compute_max_pain_picks_interior_strike():
    """Balanced OI across three strikes. Max pain should land at the
    middle strike where both sides share the pain.
    Strikes: 90 (put 10), 100 (call 10, put 10), 110 (call 10).
    Payouts:
      S=90:  call writers pay  max(90-100,0)*10 + max(90-110,0)*10 = 0+0 = 0
             put writers pay   max(90-90,0)*10  + max(100-90,0)*10  = 0+100 = 100
             total = 100
      S=100: call writers pay  max(100-100,0)*10 + max(100-110,0)*10 = 0+0 = 0
             put writers pay   max(90-100,0)*10  + max(100-100,0)*10 = 0+0 = 0
             total = 0 (minimum — max pain)
      S=110: symmetric to S=90 -> total = 100
    Expected: 100."""
    contracts = [
        (90.0, 10.0, False),
        (100.0, 10.0, True),
        (100.0, 10.0, False),
        (110.0, 10.0, True),
    ]
    assert _compute_max_pain(contracts) == 100.0


def test_compute_max_pain_differs_from_max_oi_strike():
    """Regression guard: the old implementation returned the strike
    with highest total OI (max-OI strike). Set up a case where the
    two differ.

    Max-OI strike: whichever strike has most OI overall.
    Max-pain strike: whichever minimizes writer payout.

    Construct: huge call OI at 150 (dominates total OI), small balanced
    OI lower down.
      Strikes: 100 (call 1, put 1), 150 (call 100).
    Max-OI strike = 150 (100 OI units there).
    Max pain:
      S=100: call payouts = max(100-100,0)*1 + max(100-150,0)*100 = 0
             put payouts = max(100-100,0)*1 = 0
             total = 0
      S=150: call payouts = max(150-100,0)*1 + max(150-150,0)*100 = 50
             put payouts = max(100-150,0)*1 = 0
             total = 50
    Max pain = 100. So old and new disagree: old said 150, new says 100."""
    contracts = [
        (100.0, 1.0, True),
        (100.0, 1.0, False),
        (150.0, 100.0, True),
    ]
    # New (correct) result
    assert _compute_max_pain(contracts) == 100.0
