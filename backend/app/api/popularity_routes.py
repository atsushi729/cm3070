"""UC2-C image popularity evaluation API — upload a photo, poll for results."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ImageEvaluation
from app.schemas import ImageEvaluationOut
from app.services.uploads import store_upload

router = APIRouter(prefix="/api/uc2/images", tags=["uc2-popularity"])
settings = get_settings()

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

_IMAGE_DIR = Path(settings.image_storage_dir).resolve()
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/evaluate", response_model=ImageEvaluationOut, status_code=202)
async def submit_evaluation(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Accept an uploaded photo, persist it, and enqueue the UC2-C pipeline."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"unsupported content type: {file.content_type}")

    dest, _ = store_upload(
        file.file, _IMAGE_DIR, file.filename, default_filename="photo.jpg"
    )

    try:
        from PIL import Image

        with Image.open(dest) as img:
            img.verify()
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "uploaded file is not a valid image") from exc

    ev = ImageEvaluation(storage_path=str(dest))
    db.add(ev)
    db.commit()
    db.refresh(ev)

    from app.pipelines.uc2_popularity import evaluate_image

    evaluate_image.delay(ev.id)
    return ev


@router.get("/evaluate/{evaluation_id}", response_model=ImageEvaluationOut)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db)):
    ev = db.get(ImageEvaluation, evaluation_id)
    if ev is None:
        raise HTTPException(404, "image evaluation not found")
    return ev
