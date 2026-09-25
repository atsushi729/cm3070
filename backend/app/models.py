"""Database models for reservations, reviews, and image evaluation."""
from __future__ import annotations

import enum
from datetime import datetime, date, time

from sqlalchemy import String, Integer, Text, Float, DateTime, Date, Time, Enum, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ProcessingStatus(str, enum.Enum):
    uploaded = "uploaded"          # audio stored, not yet processed
    transcribing = "transcribing"  # VAD + Whisper running
    extracting = "extracting"      # LLM entity extraction running
    pending_review = "pending_review"  # AI done, awaiting human
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited = "edited"      # human changed fields then approved
    rejected = "rejected"


class BookingStatus(str, enum.Enum):
    """Business state of the booking, separate from who/how it was reviewed.

    `review_status` is the audit trail (what the owner did); `booking_status` is
    the source of truth for "is this a live booking" (drives the calendar + the
    web bookings list).
    """
    draft = "draft"          # not yet confirmed (awaiting / failed review)
    confirmed = "confirmed"  # owner approved -> a real booking
    cancelled = "cancelled"  # rejected / withdrawn


class CalendarSyncStatus(str, enum.Enum):
    not_synced = "not_synced"  # never pushed (or event deleted)
    synced = "synced"          # mirrored to Google Calendar
    failed = "failed"          # push attempted, errored (retryable)
    disabled = "disabled"      # calendar integration off in this environment


class CallRecording(Base):
    __tablename__ = "call_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.uploaded, index=True
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    asr_latency_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reservation: Mapped["Reservation | None"] = relationship(
        back_populates="recording", uselist=False, cascade="all, delete-orphan"
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[int | None] = mapped_column(
        ForeignKey("call_recordings.id"), nullable=True
    )

    # --- AI-extracted (immutable record of what the model produced) ---
    ai_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ai_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    ai_party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Human-confirmed (what the owner approved; starts as a copy of AI) ---
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reservation_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    reservation_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.pending, index=True
    )
    has_conflict: Mapped[bool] = mapped_column(default=False)

    # --- Booking lifecycle (set when the owner confirms; drives bookings list) ---
    booking_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.draft, index=True
    )
    confirmation_ref: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Google Calendar mirror (best-effort, flag-guarded) ---
    calendar_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    calendar_html_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    calendar_sync_status: Mapped[CalendarSyncStatus] = mapped_column(
        Enum(CalendarSyncStatus), default=CalendarSyncStatus.not_synced, index=True
    )
    calendar_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calendar_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recording: Mapped["CallRecording | None"] = relationship(back_populates="reservation")


class ImageEvaluationStatus(str, enum.Enum):
    uploaded = "uploaded"
    preprocessing = "preprocessing"
    scoring = "scoring"
    explaining = "explaining"
    completed = "completed"                  # score, attributes, and VLM explanation all succeeded
    completed_partial = "completed_partial"  # score/attributes succeeded, VLM explanation failed
    failed = "failed"                        # popularity model itself failed — no usable result


class ImageEvaluation(Base):
    """One uploaded photo evaluated by UC2-C."""
    __tablename__ = "image_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[ImageEvaluationStatus] = mapped_column(
        Enum(ImageEvaluationStatus), default=ImageEvaluationStatus.uploaded, index=True
    )

    popularity_score_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    popularity_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100, calibrated
    attributes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    strengths_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    issues_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    suggestions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    vlm_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)  # popularity-model failure reason
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewSentiment(Base):
    """One customer review and its sentiment prediction."""
    __tablename__ = "review_sentiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Human feedback never overwrites the model prediction in `label`; storing
    # it separately preserves an audit trail and supplies future error examples.
    feedback_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
