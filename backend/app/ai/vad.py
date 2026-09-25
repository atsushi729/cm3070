"""Silero VAD wrapper for extracting speech before transcription."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.ai.audio import SAMPLE_RATE


@dataclass
class VadResult:
    audio: np.ndarray          # concatenated speech, 16 kHz mono float32
    speech_sec: float          # total speech duration kept
    num_segments: int


@lru_cache(maxsize=1)
def _load_model():
    # silero-vad ships a tiny (<2 MB) model; load once and cache.
    from silero_vad import load_silero_vad

    return load_silero_vad()


def extract_speech(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> VadResult:
    """Keep only speech regions of a mono waveform.

    `audio` must be float32 in [-1, 1]. Caller is responsible for resampling to
    16 kHz (see app.ai.audio.load_wav_16k).
    """
    import torch
    from silero_vad import get_speech_timestamps, collect_chunks

    model = _load_model()
    tensor = torch.from_numpy(audio).float()

    timestamps = get_speech_timestamps(
        tensor, model, sampling_rate=sample_rate, return_seconds=False
    )

    if not timestamps:
        # No speech detected — return empty so the caller can flag it.
        return VadResult(
            audio=np.zeros(0, dtype=np.float32),
            speech_sec=0.0,
            num_segments=0,
        )

    speech = collect_chunks(timestamps, tensor).numpy().astype(np.float32)
    return VadResult(
        audio=speech,
        speech_sec=len(speech) / sample_rate,
        num_segments=len(timestamps),
    )
