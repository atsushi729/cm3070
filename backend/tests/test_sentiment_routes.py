"""UC2-A review sentiment route tests. Minimal FastAPI app around just the
sentiment router (avoids app.main's lifespan), mirroring test_popularity_routes.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.ai.sentiment as sentiment_mod
from app.ai.sentiment import SentimentResult
from app.api.sentiment_routes import router as sentiment_router
from app.db import get_db
from app.models import ReviewSentiment


def _make_client(Session) -> TestClient:
    app = FastAPI()
    app.include_router(sentiment_router)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_classify_persists_row_and_returns_result(Session, monkeypatch):
    monkeypatch.setattr(
        sentiment_mod,
        "analyze_sentiment",
        lambda text: SentimentResult(label="positive", score=0.97, latency_sec=0.02),
    )
    client = _make_client(Session)

    resp = client.post("/api/uc2/reviews", json={"text": "  Great meal, lovely staff  "})

    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == "positive"
    assert body["score"] == 0.97
    assert body["latency_sec"] == 0.02
    assert body["feedback_label"] is None
    assert body["feedback_at"] is None
    assert body["text"] == "Great meal, lovely staff"  # trimmed before persist
    assert isinstance(body["id"], int)

    s = Session()
    assert s.query(ReviewSentiment).count() == 1
    s.close()


def test_classify_returns_503_when_model_unavailable(Session, monkeypatch):
    def _boom(text):
        raise RuntimeError("boom")

    monkeypatch.setattr(sentiment_mod, "analyze_sentiment", _boom)
    client = _make_client(Session)

    resp = client.post("/api/uc2/reviews", json={"text": "Great meal, lovely staff"})

    assert resp.status_code == 503
    assert "sentiment model unavailable" in resp.json()["detail"]
    s = Session()
    assert s.query(ReviewSentiment).count() == 0  # nothing persisted on failure
    s.close()


def test_classify_rejects_blank_text(Session):
    # No analyze_sentiment stub: the handler must reject blank text before it
    # ever reaches the classifier.
    client = _make_client(Session)

    resp = client.post("/api/uc2/reviews", json={"text": "   "})

    assert resp.status_code == 400
    s = Session()
    assert s.query(ReviewSentiment).count() == 0
    s.close()


def test_list_returns_newest_first_limited_with_full_counts(Session):
    s = Session()
    s.add_all([
        ReviewSentiment(text="a", label="positive", score=0.9, latency_sec=0.01,
                        created_at=datetime(2026, 1, 1, 10, 0, 0)),
        ReviewSentiment(text="b", label="positive", score=0.9, latency_sec=0.01,
                        created_at=datetime(2026, 1, 1, 11, 0, 0)),
        ReviewSentiment(text="c", label="neutral", score=0.8, latency_sec=0.01,
                        created_at=datetime(2026, 1, 1, 12, 0, 0)),
        ReviewSentiment(text="d", label="negative", score=0.7, latency_sec=0.01,
                        created_at=datetime(2026, 1, 1, 13, 0, 0)),
    ])
    s.commit()
    s.close()
    client = _make_client(Session)

    resp = client.get("/api/uc2/reviews?limit=2")

    assert resp.status_code == 200
    body = resp.json()
    assert [it["text"] for it in body["items"]] == ["d", "c"]      # newest first, capped at 2
    assert body["counts"] == {"positive": 2, "neutral": 1, "negative": 1}  # all 4 rows


def test_list_clamps_limit_and_handles_empty(Session):
    client = _make_client(Session)

    resp = client.get("/api/uc2/reviews?limit=0")

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "counts": {"positive": 0, "neutral": 0, "negative": 0}}


def test_list_clamps_upper_limit(Session):
    s = Session()
    s.add_all([
        ReviewSentiment(text="a", label="positive", score=0.9, latency_sec=0.01),
        ReviewSentiment(text="b", label="negative", score=0.7, latency_sec=0.01),
    ])
    s.commit()
    s.close()
    client = _make_client(Session)

    resp = client.get("/api/uc2/reviews?limit=9999")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["counts"] == {"positive": 1, "neutral": 0, "negative": 1}


def test_feedback_preserves_model_label_and_updates_effective_counts(Session):
    s = Session()
    row = ReviewSentiment(text="Good food, slow service", label="positive", score=0.6)
    s.add(row)
    s.commit()
    review_id = row.id
    s.close()
    client = _make_client(Session)

    resp = client.patch(
        f"/api/uc2/reviews/{review_id}/feedback", json={"label": "negative"}
    )

    assert resp.status_code == 200
    assert resp.json()["label"] == "positive"
    assert resp.json()["feedback_label"] == "negative"
    assert resp.json()["feedback_at"] is not None
    listed = client.get("/api/uc2/reviews").json()
    assert listed["counts"] == {"positive": 0, "neutral": 0, "negative": 1}


def test_feedback_same_label_records_confirmation(Session):
    s = Session()
    row = ReviewSentiment(text="Excellent", label="positive", score=0.9)
    s.add(row)
    s.commit()
    review_id = row.id
    s.close()
    client = _make_client(Session)

    resp = client.patch(
        f"/api/uc2/reviews/{review_id}/feedback", json={"label": "positive"}
    )

    assert resp.status_code == 200
    assert resp.json()["feedback_label"] == "positive"


def test_feedback_rejects_unknown_review_and_invalid_label(Session):
    client = _make_client(Session)

    assert client.patch(
        "/api/uc2/reviews/999/feedback", json={"label": "neutral"}
    ).status_code == 404
    assert client.patch(
        "/api/uc2/reviews/999/feedback", json={"label": "mixed"}
    ).status_code == 422
