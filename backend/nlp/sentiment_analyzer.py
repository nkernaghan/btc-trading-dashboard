"""Keyword-based sentiment analysis with optional FinBERT fallback."""

from __future__ import annotations

BULLISH_KEYWORDS: dict[str, float] = {
    # Price action
    "surge": 0.4, "rally": 0.4, "soar": 0.5, "breakout": 0.3,
    "bullish": 0.4, "all-time high": 0.5, "ath": 0.5, "record high": 0.5,
    "new high": 0.4, "moon": 0.3, "pump": 0.3,
    # Institutional / adoption
    "adoption": 0.3, "institutional": 0.3, "approval": 0.4,
    "etf inflow": 0.5, "etf approval": 0.5, "spot etf": 0.4,
    "strategic reserve": 0.5, "bitcoin reserve": 0.5,
    "accumulation": 0.3, "buying": 0.2, "buy": 0.2,
    # Macro bullish
    "rate cut": 0.3, "dovish": 0.3, "easing": 0.3, "stimulus": 0.3,
    "inflow": 0.3, "demand": 0.2, "support": 0.2,
    # On-chain
    "whale accumulation": 0.4, "exchange outflow": 0.3,
    "supply shock": 0.4, "halving": 0.3,
    # Regulatory positive
    "safe harbor": 0.3, "pro-crypto": 0.4, "legal clarity": 0.3,
    "stablecoin bill": 0.2, "market structure bill": 0.2,
}

BEARISH_KEYWORDS: dict[str, float] = {
    # Price action
    "crash": -0.5, "plunge": -0.4, "dump": -0.4, "bearish": -0.4,
    "sell-off": -0.4, "selloff": -0.4, "collapse": -0.5,
    "decline": -0.2, "drop": -0.2, "tumble": -0.3, "tank": -0.4,
    # Regulatory / legal
    "crackdown": -0.4, "ban": -0.5, "lawsuit": -0.3,
    "sec enforcement": -0.4, "sec": -0.2, "regulation": -0.2,
    "restrict": -0.3, "subpoena": -0.3,
    # Security
    "hack": -0.4, "exploit": -0.4, "rug pull": -0.5, "scam": -0.3,
    "vulnerability": -0.3, "breach": -0.3,
    # Market stress
    "liquidation": -0.3, "liquidated": -0.3, "fear": -0.2,
    "panic": -0.4, "capitulation": -0.4, "margin call": -0.4,
    # Macro bearish
    "tariff": -0.3, "sanctions": -0.3, "recession": -0.4,
    "rate hike": -0.3, "hawkish": -0.3, "inflation": -0.2,
    "outflow": -0.3, "etf outflow": -0.4,
    # Geopolitical
    "war": -0.3, "conflict": -0.3, "attack": -0.2, "missile": -0.3,
    "escalation": -0.3, "invasion": -0.4,
}


def analyze_headlines(articles: list[dict], max_articles: int = 20) -> float:
    """Score a batch of news articles. Returns -1.0 to +1.0.

    Averages the sentiment of individual headlines, weighting more recent
    articles slightly higher.
    """
    if not articles:
        return 0.0

    scores = []
    for article in articles[:max_articles]:
        title = article.get("title", "") or ""
        description = article.get("description", "") or ""
        # Use title primarily, description as supplement
        text = f"{title} {description[:100]}"
        score = _keyword_score(text)
        scores.append(score)

    if not scores:
        return 0.0

    # Weight recent articles higher (linear decay)
    weighted_sum = 0.0
    weight_total = 0.0
    for i, score in enumerate(scores):
        weight = max_articles - i  # newer = higher weight
        weighted_sum += score * weight
        weight_total += weight

    return max(-1.0, min(1.0, weighted_sum / weight_total)) if weight_total > 0 else 0.0

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
