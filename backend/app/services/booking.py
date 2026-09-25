"""Confirm approved reservations and check for booking conflicts."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BookingStatus, Reservation, ReviewStatus

settings = get_settings()

# Two bookings conflict if they start within this window (single-room SME default).
CONFLICT_WINDOW = timedelta(minutes=settings.booking_duration_min)


class BookingError(Exception):
    """Raised when a reservation cannot be confirmed (maps to HTTP 409)."""


def check_conflict(
    db: Session, res_date: date | None, res_time: time | None, exclude_id: int
) -> bool:
    """True if another live booking on the same date starts within the window."""
    if res_date is None or res_time is None:
        return False
    target = datetime.combine(res_date, res_time)
    # Same-date rows only; fetch just the time column rather than hydrating rows.
    times = db.execute(
        select(Reservation.reservation_time).where(
            Reservation.reservation_date == res_date,
            Reservation.review_status != ReviewStatus.rejected,
            Reservation.id != exclude_id,
            Reservation.reservation_time.is_not(None),
        )
    ).scalars().all()
    for t in times:
        other = datetime.combine(res_date, t)
        if abs((other - target).total_seconds()) < CONFLICT_WINDOW.total_seconds():
            return True
    return False


def _gen_ref() -> str:
    """Short, human-quotable confirmation code, e.g. 'R-3F9A2C'."""
    return f"R-{uuid.uuid4().hex[:6].upper()}"


def confirm_reservation(db: Session, res: Reservation) -> None:
    """Confirm an approved reservation. Idempotent; raises BookingError if invalid.

    Does NOT commit — the caller owns the transaction so the status flip and any
    enqueue happen atomically.
    """
    if res.booking_status == BookingStatus.confirmed:
        return  # already a live booking (double-click / re-approval)

    missing = [
        label
        for label, value in (
            ("date", res.reservation_date),
            ("time", res.reservation_time),
            ("party size", res.party_size),
        )
        if value is None
    ]
    if missing:
        raise BookingError(
            "cannot confirm: missing required field(s): " + ", ".join(missing)
        )

    # Re-check at approval time (the AI may have drafted this before a clashing booking).
    res.has_conflict = check_conflict(
        db, res.reservation_date, res.reservation_time, res.id
    )
    res.booking_status = BookingStatus.confirmed
    res.confirmed_at = datetime.now()
    if not res.confirmation_ref:
        res.confirmation_ref = _gen_ref()


def cancel_reservation(res: Reservation) -> None:
    """Withdraw a booking (owner rejected). Idempotent. Does NOT commit."""
    res.booking_status = BookingStatus.cancelled
