"""Mirror confirmed reservations to Google Calendar using a service account."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

from app.config import get_settings
from app.models import Reservation

settings = get_settings()

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def is_enabled() -> bool:
    """True only when the integration is switched on and fully configured."""
    return bool(
        settings.calendar_sync_enabled
        and settings.google_calendar_id
        and settings.google_credentials_path
    )


@lru_cache(maxsize=1)
def _service():
    # Imported lazily so environments without the Google libs (or with the
    # integration off) never pay the import cost.
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        settings.google_credentials_path, scopes=_SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _event_body(res: Reservation) -> dict:
    start = datetime.combine(res.reservation_date, res.reservation_time)
    end = start + timedelta(minutes=settings.booking_duration_min)
    tz = settings.calendar_timezone
    party = f"{res.party_size} guests" if res.party_size else "—"
    return {
        "summary": f"{res.name or 'Reservation'} / {party}",
        "description": (
            f"Voice reservation #{res.id}\n"
            f"Confirmation: {res.confirmation_ref or '—'}\n"
            f"Party size: {res.party_size or '—'}\n"
            "(auto-created by the Voice Reservation System)"
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
    }


def upsert_event(res: Reservation) -> dict:
    """Create or update the calendar event for a reservation.

    Idempotent on `calendar_event_id`: updates the existing event if present,
    inserts otherwise. Returns the Google event resource (has `id`, `htmlLink`).
    """
    svc = _service()
    cal_id = settings.google_calendar_id
    body = _event_body(res)
    if res.calendar_event_id:
        return (
            svc.events()
            .update(calendarId=cal_id, eventId=res.calendar_event_id, body=body)
            .execute()
        )
    return svc.events().insert(calendarId=cal_id, body=body).execute()


def delete_event(event_id: str) -> None:
    """Remove the mirrored event (booking rejected/withdrawn). 404 is benign."""
    from googleapiclient.errors import HttpError

    try:
        _service().events().delete(
            calendarId=settings.google_calendar_id, eventId=event_id
        ).execute()
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
            return  # already gone — treat as success
        raise
