"""Tests for NLP sentiment analysis and entity extraction."""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nlp.sentiment_analyzer import analyze_sentiment
from nlp.entity_extractor import extract_entities


def test_bullish_headline():
    score = analyze_sentiment(
        "Bitcoin surges past $70k as institutional demand hits record highs"
    )
    assert score > 0


def test_bearish_headline():
    score = analyze_sentiment(
        "SEC cracks down on crypto exchanges, Bitcoin plunges 10%"
    )
    assert score < 0


def test_neutral_headline():
    score = analyze_sentiment(
        "Bitcoin trading volume unchanged as markets await Fed decision"
    )
    assert -0.3 <= score <= 0.3


def test_trump_positive():
    score = analyze_sentiment(
        "Trump signs executive order establishing Bitcoin strategic reserve"
    )
    assert score > 0


def test_tariff_negative():
    score = analyze_sentiment(
        "Trump announces 50% tariffs on all imports, markets crash"
    )
    assert score < 0


def test_extract_entities():
    entities = extract_entities(
        "Fed Chair Powell signals rate cut as Trump pushes for Bitcoin reserve "
        "and SEC drops crypto lawsuit"
    )
    assert "fed" in entities
    assert "trump" in entities
    assert "sec" in entities
    assert "bitcoin" in entities
