"""ReviewSentiment model round-trip tests."""
from __future__ import annotations

from app.models import ReviewSentiment


def test_review_sentiment_row_roundtrips(db):
    row = ReviewSentiment(text="tasty and warm", label="positive", score=0.95, latency_sec=0.03)
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.id is not None
    assert row.created_at is not None

    fetched = db.get(ReviewSentiment, row.id)
    assert fetched.text == "tasty and warm"
    assert fetched.label == "positive"
    assert fetched.score == 0.95
    assert fetched.latency_sec == 0.03


def test_review_sentiment_allows_null_result_fields(db):
    row = ReviewSentiment(text="", label=None, score=None, latency_sec=None)
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.label is None
    assert row.score is None
