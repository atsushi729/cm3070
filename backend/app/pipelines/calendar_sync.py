"""Google Calendar sync tasks (best-effort, retrying).

Enqueued by the review API after a reservation is confirmed/rejected. Kept off
the request path so a calendar outage never blocks a booking; the DB stays the
source of truth and `calendar_sync_status` records the outcome for the UI (and a
manual `/resync`).
"""
from __future__ import annotations

from datetime import datetime

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models import CalendarSyncStatus, Reservation

# Shared retry policy for the calendar tasks (one online dependency, so retry
# with backoff). Kept in one place so the two tasks can't drift apart.
_RETRY_OPTS = dict(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)


@celery_app.task(name="calendar.sync_reservation", **_RETRY_OPTS)
def sync_reservation_to_calendar(reservation_id: int) -> dict:
    from app.services import calendar as cal

    db = SessionLocal()
    try:
        res = db.get(Reservation, reservation_id)
        if res is None:
            return {"error": f"reservation {reservation_id} not found"}

        if not cal.is_enabled():
            res.calendar_sync_status = CalendarSyncStatus.disabled
            db.commit()
            return {"reservation_id": reservation_id, "status": "disabled"}

        try:
            event = cal.upsert_event(res)
            res.calendar_event_id = event.get("id")
            res.calendar_html_link = event.get("htmlLink")
            res.calendar_sync_status = CalendarSyncStatus.synced
            res.calendar_synced_at = datetime.now()
            res.calendar_sync_error = None
            db.commit()
            return {
                "reservation_id": reservation_id,
                "status": "synced",
                "event_id": res.calendar_event_id,
            }
        except Exception as exc:  # noqa: BLE001 — record + re-raise so Celery retries
            res.calendar_sync_status = CalendarSyncStatus.failed
            res.calendar_sync_error = str(exc)
            db.commit()
            raise
    finally:
        db.close()


@celery_app.task(name="calendar.remove_reservation", **_RETRY_OPTS)
def remove_reservation_from_calendar(reservation_id: int) -> dict:
    from app.services import calendar as cal

    db = SessionLocal()
    try:
        res = db.get(Reservation, reservation_id)
        if res is None:
            return {"error": f"reservation {reservation_id} not found"}
        if not res.calendar_event_id or not cal.is_enabled():
            return {"reservation_id": reservation_id, "status": "noop"}

        cal.delete_event(res.calendar_event_id)
        res.calendar_event_id = None
        res.calendar_html_link = None
        res.calendar_sync_status = CalendarSyncStatus.not_synced
        res.calendar_sync_error = None
        db.commit()
        return {"reservation_id": reservation_id, "status": "removed"}
    finally:
        db.close()
