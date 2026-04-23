# TODO

Follow-ups deferred from the 2026-04-23 Codex audit. Each item is acceptable
as-is today; these are the tracked improvements to pick up next.

## Fix #1 — Polarity keyword gaps

`backend/data/sentiment.py:_classify_polarity` returns `"unknown"` on
several common Polymarket framings, which means the vote is skipped
rather than sign-flipped. Correct conservative behavior, but it leaves
real signal on the floor.

Known gaps with failing tests ready to flip:
- Strategic reserve / Bitcoin reserve (bull)
- Corporate treasury additions (bull)
- Buy / accumulate phrasings (bull)
- Reject / deny / block phrasings (bear)

Next step: extend `_POLY_ACTION_BULL` and `_POLY_ACTION_BEAR` with the
above keywords. Tests in `tests/test_polymarket_polarity.py` currently
pin these to `"unknown"` — inverting those asserts is the acceptance
criterion.

## Fix #2 — `legs_included` not surfaced

The options fetcher computes `legs_included` but it does not reach the
engine or the UI. Observability gap only — the underlying data is
correct.

Next step: propagate `legs_included` through to the engine's vote
metadata so dashboards can show how many option legs fed into the max-
pain calculation.

## Fix #3 — Mean-of-3 vs median/trimmed mean + "4x OI" wording

Current aggregation across OI venues is an arithmetic mean over up to
three venues (not four; the commit message overstated it). A single-
venue outlier moves the aggregate meaningfully.

Next step: switch to median or a 20% trimmed mean once we routinely get
four or more venues reporting. Separately, fix the stale "4x OI" wording
in the earlier commit description (amending history is intentionally not
done — noted here instead).

## Fix #5 — Under-tested

The composite path was under-tested before the audit's fix landed and
still is. No regression; the fix didn't reduce coverage, it just didn't
add any.

Next step: add integration tests that exercise the full composite →
signal generator path with realistic vote distributions, not just the
unit-level scoring tests that exist today.

## Fix #9 — Narrow bear band

The bear band for one of the voting indicators (see `engine.py` band
definitions) is narrow by design — the indicator rarely reads that deep
into bearish territory, and widening the band would dilute the signal
when it does. Not broken, just sparse.

Next step: revisit only if post-ship PnL data shows the vote firing far
less often than simulated. No code change until then.

---

## Recently closed (for reference)

- **Must-fix #4** — 1m ring buffer extended from 10 → 1440 bars so old
  SL/TP wicks stay visible to the outcome tracker. Commit `cc96f3c`.
- **Must-fix #7** — `etf:flows` is now single-writer (Yahoo only); the
  onchain and news dual-writers were deleted so the freshness stamp
  means "Yahoo ETF is healthy" again. Commit `21c27d4`.
- **Test gaps** — `drop_unclosed` boundary + 4h/1d coverage (commit
  `97a7e04`); direct `_classify_polarity` tests covering phrasings,
  direction precedence, word-boundary correctness (commit `a80afa9`).
