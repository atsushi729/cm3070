"""Pydantic API schemas."""
from __future__ import annotations

from datetime import datetime, date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    BookingStatus, CalendarSyncStatus, ImageEvaluationStatus, ProcessingStatus, ReviewStatus,
)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recording_id: int | None
    ai_name: str | None
    ai_date: date | None
    ai_time: time | None
    ai_party_size: int | None
    ai_confidence: float | None
    name: str | None
    reservation_date: date | None
    reservation_time: time | None
    party_size: int | None
    review_status: ReviewStatus
    has_conflict: bool
    created_at: datetime

    # Booking + calendar mirror
    booking_status: BookingStatus
    confirmation_ref: str | None
    confirmed_at: datetime | None
    calendar_event_id: str | None
    calendar_html_link: str | None
    calendar_sync_status: CalendarSyncStatus
    calendar_synced_at: datetime | None


class ReservationReviewIn(BaseModel):
    """Owner's review action from the Voice Reservation System screen."""
    action: ReviewStatus  # approved | edited | rejected
    name: str | None = None
    reservation_date: date | None = None
    reservation_time: time | None = None
    party_size: int | None = None


class RecordingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: ProcessingStatus
    transcript: str | None
    language: str | None
    duration_sec: float | None
    asr_latency_sec: float | None
    error: str | None
    created_at: datetime


class ImageEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ImageEvaluationStatus
    popularity_score: float | None
    popularity_score_raw: float | None
    attributes_json: dict | None
    strengths_json: list | None
    issues_json: list | None
    suggestions_json: list | None
    vlm_error: str | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ReviewSentimentIn(BaseModel):
    """One review submitted from the Review Sentiment screen."""
    text: str = Field(max_length=5000)


class ReviewSentimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    label: str | None
    score: float | None
    latency_sec: float | None
    feedback_label: str | None
    feedback_at: datetime | None
    created_at: datetime


class ReviewSentimentFeedbackIn(BaseModel):
    """Human-confirmed label; equal to the model label means "correct"."""
    label: Literal["positive", "neutral", "negative"]


class ReviewSentimentCounts(BaseModel):
    positive: int
    neutral: int
    negative: int


class ReviewSentimentListOut(BaseModel):
    items: list[ReviewSentimentOut]
    counts: ReviewSentimentCounts
