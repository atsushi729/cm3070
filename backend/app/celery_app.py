"""Celery queue for background inference and calendar synchronization."""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sme",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.pipelines.uc1", "app.pipelines.calendar_sync", "app.pipelines.uc2_popularity"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Keep this checkout's jobs away from other local Celery apps sharing Redis.
    task_default_queue="cm3070_ai",
    # Serialize heavy models on the 16 GB host.
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
)
