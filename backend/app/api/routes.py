"""UC1 REST API — upload calls, list/review reservations."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import BookingStatus, CallRecording, Reservation, ReviewStatus
from app.schemas import RecordingOut, ReservationOut, ReservationReviewIn
from app.services.booking import BookingError, cancel_reservation, confirm_reservation
from app.services.uploads import store_upload

router = APIRouter(prefix="/api", tags=["uc1"])
settings = get_settings()

_AUDIO_DIR = Path(settings.audio_storage_dir).resolve()
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/recordings", response_model=dict)
async def upload_recording(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Accept a phone-call audio file, persist it, and enqueue the UC1 pipeline."""
    dest, filename = store_upload(
        file.file, _AUDIO_DIR, file.filename, default_filename="call.wav"
    )

    rec = CallRecording(filename=filename, storage_path=str(dest))
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Enqueue async processing (Celery). Import here to avoid loading at web boot.
    from app.pipelines.uc1 import process_recording

    task = process_recording.delay(rec.id)
    return {"recording_id": rec.id, "task_id": task.id, "status": rec.status.value}


@router.get("/recordings", response_model=list[RecordingOut])
def list_recordings(db: Session = Depends(get_db)):
    return db.execute(select(CallRecording).order_by(CallRecording.created_at.desc())).scalars().all()


@router.get("/recordings/{recording_id}", response_model=RecordingOut)
def get_recording(recording_id: int, db: Session = Depends(get_db)):
    rec = db.get(CallRecording, recording_id)
    if rec is None:
        raise HTTPException(404, "recording not found")
    return rec


@router.get("/recordings/{recording_id}/audio")
def get_recording_audio(recording_id: int, db: Session = Depends(get_db)):
    rec = db.get(CallRecording, recording_id)
    if rec is None or not Path(rec.storage_path).exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(rec.storage_path, filename=rec.filename)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(status: ReviewStatus | None = None, db: Session = Depends(get_db)):
    stmt = select(Reservation).order_by(Reservation.created_at.desc())
    if status is not None:
        stmt = stmt.where(Reservation.review_status == status)
    return db.execute(stmt).scalars().all()


@router.post("/reservations/{reservation_id}/review", response_model=ReservationOut)
def review_reservation(
    reservation_id: int, payload: ReservationReviewIn, db: Session = Depends(get_db)
):
    """Apply the review action and update the booking and calendar mirror."""
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(404, "reservation not found")
    # Pydantic already enforces the enum; only `pending` is a valid value that
    # isn't a real review action.
    if payload.action == ReviewStatus.pending:
        raise HTTPException(422, "action must be approved, edited, or rejected")

    if payload.action == ReviewStatus.edited:
        # apply human corrections to the confirmed fields (AI fields stay intact)
        if payload.name is not None:
            res.name = payload.name
        if payload.reservation_date is not None:
            res.reservation_date = payload.reservation_date
        if payload.reservation_time is not None:
            res.reservation_time = payload.reservation_time
        if payload.party_size is not None:
            res.party_size = payload.party_size

    res.review_status = payload.action
    res.reviewed_at = datetime.now()

    # --- Booking processing: confirm or cancel ---
    if payload.action == ReviewStatus.rejected:
        cancel_reservation(res)
    else:  # approved | edited
        try:
            confirm_reservation(db, res)
        except BookingError as exc:
            db.rollback()
            raise HTTPException(409, str(exc))
    had_event = res.calendar_event_id is not None

    db.commit()
    db.refresh(res)

    # Mirror to Google Calendar off the request path (the task no-ops if the
    # integration is disabled). Imported here to keep it out of the web boot path.
    from app.pipelines.calendar_sync import (
        remove_reservation_from_calendar,
        sync_reservation_to_calendar,
    )

    if payload.action == ReviewStatus.rejected:
        if had_event:
            remove_reservation_from_calendar.delay(res.id)
    else:
        sync_reservation_to_calendar.delay(res.id)

    return res


@router.post("/reservations/{reservation_id}/resync", response_model=ReservationOut)
def resync_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """Manually re-push a confirmed booking to Google Calendar (after a failure)."""
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(404, "reservation not found")
    if res.booking_status != BookingStatus.confirmed:
        raise HTTPException(409, "only confirmed bookings can be synced")

    from app.pipelines.calendar_sync import sync_reservation_to_calendar

    sync_reservation_to_calendar.delay(res.id)
    return res
