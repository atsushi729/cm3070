"""UC2-A review sentiment API — classify one review synchronously, list history.

Classification runs inline in the request rather than on a Celery worker.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.sentiment import LABELS  # canonical label set (no transformers import)
from app.db import get_db
from app.models import ReviewSentiment
from app.schemas import (
    ReviewSentimentFeedbackIn,
    ReviewSentimentIn,
    ReviewSentimentListOut,
    ReviewSentimentOut,
)

router = APIRouter(prefix="/api/uc2/reviews", tags=["uc2-sentiment"])

# Serialize classification: two concurrent cold requests would otherwise both
# trigger a full mBERT load (functools.lru_cache is not load-atomic). Warm p50
# is ~23 ms on single-tenant localhost, so serializing the whole call is fine.
_classify_lock = threading.Lock()


@router.post("", response_model=ReviewSentimentOut, status_code=201)
def classify_review(payload: ReviewSentimentIn, db: Session = Depends(get_db)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "review text must not be empty")

    # Lazy import: keep transformers out of the web process until first use.
    from app.ai import sentiment as sentiment_mod

    try:
        with _classify_lock:
            result = sentiment_mod.analyze_sentiment(text)
    except Exception as exc:  # noqa: BLE001 — surface model/runtime failure to the UI
        raise HTTPException(503, f"sentiment model unavailable: {exc}") from exc

    row = ReviewSentiment(
        text=text,
        label=result.label,
        score=result.score,
        latency_sec=result.latency_sec,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=ReviewSentimentListOut)
def list_reviews(limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))

    items = (
        db.query(ReviewSentiment)
        .order_by(ReviewSentiment.created_at.desc(), ReviewSentiment.id.desc())
        .limit(limit)
        .all()
    )

    effective_label = func.coalesce(
        ReviewSentiment.feedback_label, ReviewSentiment.label
    )
    rows = db.execute(
        select(effective_label, func.count()).group_by(effective_label)
    ).all()
    tally = {label: n for label, n in rows}
    counts = {label: tally.get(label, 0) for label in LABELS}
    return {"items": items, "counts": counts}


@router.patch("/{review_id}/feedback", response_model=ReviewSentimentOut)
def record_feedback(
    review_id: int,
    payload: ReviewSentimentFeedbackIn,
    db: Session = Depends(get_db),
):
    """Store the human-confirmed label without replacing the AI prediction."""
    row = db.get(ReviewSentiment, review_id)
    if row is None:
        raise HTTPException(404, "review sentiment result not found")
    row.feedback_label = payload.label
    row.feedback_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row
