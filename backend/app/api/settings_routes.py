"""Read-only integration status; never exposes credentials or identifiers."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db, is_db_healthy
from app.services import calendar

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/status")
def get_status(db: Session = Depends(get_db)) -> dict:
    return {
        "db": is_db_healthy(db),
        "calendar_sync_enabled": calendar.is_enabled(),
    }
