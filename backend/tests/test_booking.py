"""Booking confirmation service tests (app/services/booking.py)."""
from __future__ import annotations

from datetime import time

import pytest

from app.models import BookingStatus, ReviewStatus
from app.services.booking import (
    BookingError,
    cancel_reservation,
    check_conflict,
    confirm_reservation,
)
from tests.conftest import make_reservation


def test_confirm_marks_booking_and_stamps_ref(db):
    res = make_reservation()
    db.add(res)
    db.flush()

    confirm_reservation(db, res)
    db.commit()

    assert res.booking_status == BookingStatus.confirmed
    assert res.confirmed_at is not None
    assert res.confirmation_ref and res.confirmation_ref.startswith("R-")


def test_confirm_missing_fields_raises(db):
    res = make_reservation(res_time=None)  # no time -> cannot book
    db.add(res)
    db.flush()

    with pytest.raises(BookingError) as exc:
        confirm_reservation(db, res)
    assert "time" in str(exc.value)
    assert res.booking_status == BookingStatus.draft


def test_confirm_is_idempotent(db):
    res = make_reservation()
    db.add(res)
    db.flush()

    confirm_reservation(db, res)
    first_ref = res.confirmation_ref
    confirm_reservation(db, res)  # second approval / double-click

    assert res.confirmation_ref == first_ref  # ref not regenerated


def test_confirm_rechecks_conflict_at_approval_time(db):
    # An existing live booking at 19:00 ...
    existing = make_reservation(
        res_time=time(19, 0),
        review_status=ReviewStatus.approved,
        booking_status=BookingStatus.confirmed,
    )
    db.add(existing)
    db.flush()

    # ... a new draft at 19:30 had no conflict when first drafted.
    new = make_reservation(res_time=time(19, 30))
    new.has_conflict = False
    db.add(new)
    db.flush()

    confirm_reservation(db, new)
    assert new.has_conflict is True  # detected on confirm


def test_cancel_sets_cancelled(db):
    res = make_reservation()
    db.add(res)
    db.flush()

    cancel_reservation(res)
    assert res.booking_status == BookingStatus.cancelled


def test_check_conflict_ignores_rejected_and_self(db):
    rejected = make_reservation(
        res_time=time(19, 15), review_status=ReviewStatus.rejected
    )
    db.add(rejected)
    target = make_reservation(res_time=time(19, 0))
    db.add(target)
    db.flush()

    # Only the rejected row is nearby -> no conflict.
    assert check_conflict(db, target.reservation_date, time(19, 0), target.id) is False
