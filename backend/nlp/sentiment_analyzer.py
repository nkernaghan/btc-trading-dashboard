"""Keyword-based sentiment analysis with optional FinBERT fallback."""

from __future__ import annotations

BULLISH_KEYWORDS: dict[str, float] = {
    "surge": 0.4,
    "rally": 0.4,
    "soar": 0.5,
    "breakout": 0.3,
    "bullish": 0.4,
    "all-time high": 0.5,
    "ath": 0.5,
    "adoption": 0.3,
    "institutional": 0.3,
    "approval": 0.4,
    "reserve": 0.4,
    "rate cut": 0.3,
    "inflow": 0.3,
    "accumulation": 0.3,
    "demand": 0.2,
    "support": 0.2,
    "record": 0.3,
    "buy": 0.2,
    "strategic reserve": 0.5,
}

BEARISH_KEYWORDS: dict[str, float] = {
    "crash": -0.5,
    "plunge": -0.4,
    "dump": -0.4,
    "bearish": -0.4,
    "sell-off": -0.4,
    "crackdown": -0.4,
    "ban": -0.5,
    "lawsuit": -0.3,
    "hack": -0.4,
    "exploit": -0.4,
    "liquidation": -0.3,
    "fear": -0.2,
    "panic": -0.4,
    "collapse": -0.5,
    "tariff": -0.3,
    "sanctions": -0.3,
    "recession": -0.4,
    "rate hike": -0.3,
    "outflow": -0.3,
    "sec": -0.2,
    "regulation": -0.2,
    "restrict": -0.3,
    "war": -0.3,
    "conflict": -0.3,
    "decline": -0.2,
    "drop": -0.2,
}

# Lazy-loaded FinBERT pipeline
_finbert_pipeline = None
_finbert_load_attempted = False


def _try_load_finbert():
    """Attempt to load FinBERT model. Returns pipeline or None."""
    global _finbert_pipeline, _finbert_load_attempted
    if _finbert_load_attempted:
        return _finbert_pipeline
    _finbert_load_attempted = True
    try:
        from transformers import pipeline

        _finbert_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            top_k=None,
        )
    except Exception:
        _finbert_pipeline = None
    return _finbert_pipeline


def _finbert_score(text: str) -> float | None:
    """Score text using FinBERT. Returns float in [-1, 1] or None on failure."""
    pipe = _try_load_finbert()
    if pipe is None:
        return None
    try:
        results = pipe(text[:512])  # FinBERT max length
        if not results:
            return None
        scores = results[0] if isinstance(results[0], list) else results
        score_map: dict[str, float] = {}
        for item in scores:
            score_map[item["label"].lower()] = item["score"]
        positive = score_map.get("positive", 0.0)
        negative = score_map.get("negative", 0.0)
        return positive - negative
    except Exception:
        return None


def _keyword_score(text: str) -> float:
    """Score text using keyword matching. Returns float clamped to [-1, 1]."""
    text_lower = text.lower()
    total = 0.0

    # Check multi-word keywords first (longer phrases), then single words
    all_keywords = list(BULLISH_KEYWORDS.items()) + list(BEARISH_KEYWORDS.items())
    # Sort by keyword length descending so longer phrases match first
    all_keywords.sort(key=lambda x: len(x[0]), reverse=True)

    for keyword, weight in all_keywords:
        if keyword in text_lower:
            total += weight

    return max(-1.0, min(1.0, total))


def analyze_sentiment(text: str) -> float:
    """Returns -1.0 (bearish) to +1.0 (bullish).

    Try FinBERT first (lazy-loaded), fallback to keyword scoring.
    Keyword scoring: sum all matching keyword weights, clamp to [-1, 1].
    """
    finbert_result = _finbert_score(text)
    if finbert_result is not None:
        return finbert_result
    return _keyword_score(text)
