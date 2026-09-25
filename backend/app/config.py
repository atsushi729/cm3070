"""Application settings, loaded from environment / backend/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Infra
    database_url: str = "postgresql+psycopg://sme:sme_dev_pw@localhost:5432/sme"
    redis_url: str = "redis://localhost:6379/0"

    # Local AI
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # Fine-tuned weights live under backend/data/models.
    sentiment_model_path: str = "./data/models/sentiment-mbert"
    sentiment_finetune_base: str = "bert-base-multilingual-cased"
    sentiment_baseline_model: str = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"

    # App
    app_env: str = "development"
    audio_storage_dir: str = "./data/audio"

    # Booking
    booking_duration_min: int = 90  # default seating length; also the conflict window

    # Google Calendar mirror (off by default so offline eval is never blocked).
    # Service-account auth: share the target calendar with the SA's email address.
    calendar_sync_enabled: bool = False
    google_calendar_id: str = ""               # e.g. "xxx@group.calendar.google.com"
    google_credentials_path: str = ""          # path to the service-account JSON key
    calendar_timezone: str = "Asia/Tokyo"      # IANA tz for event start/end

    # Pretrained ResNet50 popularity model; weights are downloaded locally.
    popularity_model_path: str = "./data/models/popularity-resnet50/model-resnet50.pth"
    # Calibration bounds measured on 40 generic stock photos; replace with venue data.
    popularity_score_min: float = 0.9616
    popularity_score_max: float = 6.8906

    # Vision-language model for photo suggestions.
    vlm_model: str = "qwen2.5vl:7b"

    image_storage_dir: str = "./data/uc2_images"

    # Offline suggestion-quality evaluation only.
    openai_api_key: str = ""
    llm_eval_model: str = "gpt-4o"


@lru_cache
def get_settings() -> Settings:
    return Settings()
