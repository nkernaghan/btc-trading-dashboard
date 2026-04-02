"""Keyword-based entity extraction from news headlines."""

ENTITY_KEYWORDS: dict[str, list[str]] = {
    "trump": ["trump", "president", "white house", "executive order"],
    "fed": ["fed", "federal reserve", "powell", "fomc", "rate cut", "rate hike", "monetary policy"],
    "sec": ["sec", "securities and exchange", "gensler", "crypto regulation"],
    "tariff": ["tariff", "trade war", "import tax", "duties", "trade policy"],
    "etf": ["etf", "spot bitcoin", "blackrock", "fidelity", "grayscale", "fund flow"],
    "bitcoin": ["bitcoin", "btc", "crypto", "cryptocurrency"],
    "regulation": ["regulation", "regulatory", "compliance", "ban", "restrict", "lawsuit"],
    "war": ["war", "conflict", "military", "geopolitical", "sanctions"],
    "treasury": ["treasury", "yellen", "debt ceiling", "government spending"],
}


def extract_entities(text: str) -> list[str]:
    """Extract relevant entity keys from text. Case-insensitive matching."""
    text_lower = text.lower()
    matched: list[str] = []
    for entity, keywords in ENTITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(entity)
                break
    return matched
