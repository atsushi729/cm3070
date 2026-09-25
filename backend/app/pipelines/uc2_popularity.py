"""Evaluate a photo and keep its score if VLM explanation fails."""
from __future__ import annotations

from datetime import datetime

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models import ImageEvaluation, ImageEvaluationStatus


@celery_app.task(name="uc2.evaluate_image")
def evaluate_image(evaluation_id: int) -> dict:
    # Import heavy AI modules lazily so the web process never loads them.
    from PIL import Image

    from app.ai import popularity as popularity_mod
    from app.ai import vlm as vlm_mod
    from app.services import attributes as attributes_mod

    db = SessionLocal()
    try:
        ev = db.get(ImageEvaluation, evaluation_id)
        if ev is None:
            return {"error": f"image evaluation {evaluation_id} not found"}

        # --- Stage 1: load image ---
        ev.status = ImageEvaluationStatus.preprocessing
        db.commit()
        image = Image.open(ev.storage_path)

        # --- Stage 2: popularity score + pixel attributes ---
        ev.status = ImageEvaluationStatus.scoring
        db.commit()
        raw_score = popularity_mod.score(image)
        ev.popularity_score_raw = raw_score
        ev.popularity_score = popularity_mod.calibrate(raw_score)
        ev.attributes_json = attributes_mod.extract(image)
        db.commit()

        # --- Stage 3: VLM explanation (best-effort — score/attributes stand alone) ---
        ev.status = ImageEvaluationStatus.explaining
        db.commit()
        try:
            explanation = vlm_mod.explain(
                ev.storage_path, ev.popularity_score, ev.attributes_json
            )
            ev.strengths_json = explanation.strengths
            ev.issues_json = explanation.issues
            ev.suggestions_json = explanation.suggestions
            ev.status = ImageEvaluationStatus.completed
        except Exception as exc:  # noqa: BLE001 — VLM failure degrades, doesn't fail the run
            ev.vlm_error = str(exc)
            ev.status = ImageEvaluationStatus.completed_partial

        ev.finished_at = datetime.now()
        db.commit()

        return {
            "evaluation_id": ev.id,
            "status": ev.status.value,
            "popularity_score": ev.popularity_score,
        }
    except Exception as exc:  # noqa: BLE001 — record failure for the API/UI
        db.rollback()
        ev = db.get(ImageEvaluation, evaluation_id)
        if ev is not None:
            ev.status = ImageEvaluationStatus.failed
            ev.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()
