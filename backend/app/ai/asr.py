"""faster-whisper ASR wrapper."""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.config import get_settings

_settings = get_settings()
_LOCAL_SMALL_MODEL = Path(__file__).resolve().parents[2] / "data/models/faster-whisper-small"

# Bias transcription toward common Japanese surnames without forcing them into the text.
_SURNAME_HOTWORDS = " ".join([
    "佐藤", "鈴木", "高橋", "田中", "渡辺", "伊藤", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水",
])


@dataclass
class TranscriptResult:
    text: str
    language: str
    latency_sec: float


@lru_cache(maxsize=1)
def _load_model(model_size: str | None = None):
    from faster_whisper import WhisperModel

    device = _settings.whisper_device
    compute_type = _settings.whisper_compute_type
    if device == "auto":
        # CTranslate2 has no Metal backend; CPU int8 is the fast path on M-series.
        device = "cpu"
    model_source = model_size or _settings.whisper_model
    # `make up` downloads the selected production model to this pinned local
    # directory. Keep accepting aliases such as "tiny" for evaluation runs.
    if model_source == "small" and (_LOCAL_SMALL_MODEL / "model.bin").is_file():
        model_source = str(_LOCAL_SMALL_MODEL)
    return WhisperModel(model_source, device=device, compute_type=compute_type)


def unload() -> None:
    """Free Whisper before the LLM loads to avoid memory pressure."""
    import gc

    _load_model.cache_clear()
    gc.collect()


def transcribe(audio: np.ndarray, language: str | None = None,
               model_size: str | None = None) -> TranscriptResult:
    """Transcribe a 16 kHz mono float32 waveform; detect language if unset."""
    model = _load_model(model_size)
    start = time.perf_counter()
    segments, info = model.transcribe(
        audio,
        language=language,
        vad_filter=False,           # VAD already applied upstream (app.ai.vad)
        beam_size=5,
        condition_on_previous_text=False,
        hotwords=_SURNAME_HOTWORDS,
    )
    text = "".join(seg.text for seg in segments).strip()
    latency = time.perf_counter() - start
    return TranscriptResult(text=text, language=info.language, latency_sec=latency)
