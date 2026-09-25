"""Audio loading helpers — decode arbitrary input to 16 kHz mono float32.

Uses ffmpeg (already required by faster-whisper) so we accept wav/mp3/m4a/ogg
phone-recording formats without extra Python codecs.
"""
from __future__ import annotations

import subprocess

import numpy as np

SAMPLE_RATE = 16_000


def load_wav_16k(path: str) -> np.ndarray:
    """Decode any ffmpeg-readable file to a 16 kHz mono float32 numpy array."""
    cmd = [
        "ffmpeg", "-nostdin", "-threads", "1",
        "-i", path,
        "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def duration_sec(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    return len(audio) / sample_rate
