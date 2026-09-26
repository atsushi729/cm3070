"""Process call audio into a reservation awaiting human review."""
from __future__ import annotations

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models import CallRecording, Reservation, ProcessingStatus, ReviewStatus
from app.services.booking import check_conflict


@celery_app.task(name="uc1.process_recording")
def process_recording(recording_id: int) -> dict:
    # Import heavy AI modules lazily so the web process never loads them.
    from app.ai import extract as extract_mod
    from app.ai.pipeline import transcribe_audio_file

    db = SessionLocal()
    try:
        rec = db.get(CallRecording, recording_id)
        if rec is None:
            return {"error": f"recording {recording_id} not found"}

        # --- Stage 1: VAD + ASR (unloads Whisper before returning) ---
        rec.status = ProcessingStatus.transcribing
        db.commit()

        at = transcribe_audio_file(rec.storage_path)
        tr = at.transcript
        rec.duration_sec = at.duration_sec
        rec.transcript = tr.text
        rec.language = tr.language
        rec.asr_latency_sec = tr.latency_sec
        db.commit()

        # --- Stage 2: LLM entity extraction ---
        rec.status = ProcessingStatus.extracting
        db.commit()

        fields = extract_mod.extract_reservation(tr.text)

        reservation = Reservation(
            recording_id=rec.id,
            ai_name=fields.name,
            ai_date=fields.date,
            ai_time=fields.time,
            ai_party_size=fields.party_size,
            ai_confidence=fields.confidence,
            ai_raw_json=fields.raw,
            name=fields.name,
            reservation_date=fields.date,
            reservation_time=fields.time,
            party_size=fields.party_size,
            review_status=ReviewStatus.pending,
        )
        db.add(reservation)
        db.flush()  # assign id for conflict self-exclusion
        reservation.has_conflict = check_conflict(
            db, fields.date, fields.time, reservation.id
        )

        rec.status = ProcessingStatus.pending_review
        db.commit()

        return {
            "recording_id": rec.id,
            "reservation_id": reservation.id,
            "transcript": tr.text,
            "language": tr.language,
            "extracted": {
                "name": fields.name,
                "date": str(fields.date) if fields.date else None,
                "time": str(fields.time) if fields.time else None,
                "party_size": fields.party_size,
                "confidence": fields.confidence,
            },
            "has_conflict": reservation.has_conflict,
            "asr_latency_sec": round(tr.latency_sec, 2),
            "llm_latency_sec": round(fields.latency_sec, 2),
        }
    except Exception as exc:  # noqa: BLE001 — record failure for the UI
        db.rollback()
        rec = db.get(CallRecording, recording_id)
        if rec is not None:
            rec.status = ProcessingStatus.failed
            rec.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()
