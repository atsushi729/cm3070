"""Calendar sync Celery task tests (app/pipelines/calendar_sync.py).

The Google Calendar service is mocked — these tests assert the task's bookkeeping
(event id + sync status) without any network calls. SessionLocal is patched to the
in-memory test sessionmaker.
"""
from __future__ import annotations

import pytest

from app.models import BookingStatus, CalendarSyncStatus, Reservation, ReviewStatus
from app.pipelines import calendar_sync
from app.services import calendar as cal
from tests.conftest import make_reservation


@pytest.fixture
def seed(Session, monkeypatch):
    """Patch the task's SessionLocal to the test DB and return a seeder."""
    monkeypatch.setattr(calendar_sync, "SessionLocal", Session)

    def _seed(**kw) -> int:
        s = Session()
        res = make_reservation(
            review_status=ReviewStatus.approved,
            booking_status=BookingStatus.confirmed,
            **kw,
        )
        s.add(res)
        s.commit()
        rid = res.id
        s.close()
        return rid

    return _seed


def _get(Session, rid) -> Reservation:
    s = Session()
    try:
        return s.get(Reservation, rid)
    finally:
        s.close()


def test_sync_disabled_marks_disabled(seed, Session, monkeypatch):
    monkeypatch.setattr(cal, "is_enabled", lambda: False)
    rid = seed()

    out = calendar_sync.sync_reservation_to_calendar.run(rid)

    assert out["status"] == "disabled"
    assert _get(Session, rid).calendar_sync_status == CalendarSyncStatus.disabled


def test_sync_success_stores_event(seed, Session, monkeypatch):
    monkeypatch.setattr(cal, "is_enabled", lambda: True)
    monkeypatch.setattr(
        cal,
        "upsert_event",
        lambda res: {"id": "evt_123", "htmlLink": "https://cal/evt_123"},
    )
    rid = seed()

    out = calendar_sync.sync_reservation_to_calendar.run(rid)

    res = _get(Session, rid)
    assert out["status"] == "synced"
    assert res.calendar_event_id == "evt_123"
    assert res.calendar_html_link == "https://cal/evt_123"
    assert res.calendar_sync_status == CalendarSyncStatus.synced
    assert res.calendar_synced_at is not None


def test_sync_failure_marks_failed(seed, Session, monkeypatch):
    monkeypatch.setattr(cal, "is_enabled", lambda: True)

    def boom(res):
        raise RuntimeError("api down")

    monkeypatch.setattr(cal, "upsert_event", boom)
    rid = seed()

    # The task records the failure then re-raises (Celery retry kicks in).
    with pytest.raises(Exception):
        calendar_sync.sync_reservation_to_calendar.run(rid)

    res = _get(Session, rid)
    assert res.calendar_sync_status == CalendarSyncStatus.failed
    assert "api down" in (res.calendar_sync_error or "")


def test_remove_clears_event(seed, Session, monkeypatch):
    monkeypatch.setattr(cal, "is_enabled", lambda: True)
    deleted: list[str] = []
    monkeypatch.setattr(cal, "delete_event", lambda eid: deleted.append(eid))
    rid = seed()
    # give it an event id to remove
    s = Session()
    r = s.get(Reservation, rid)
    r.calendar_event_id = "evt_123"
    r.calendar_sync_status = CalendarSyncStatus.synced
    s.commit()
    s.close()

    out = calendar_sync.remove_reservation_from_calendar.run(rid)

    res = _get(Session, rid)
    assert out["status"] == "removed"
    assert deleted == ["evt_123"]
    assert res.calendar_event_id is None
    assert res.calendar_sync_status == CalendarSyncStatus.not_synced
