"""Shared audio loading, VAD, and transcription steps."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ai import audio as audio_mod
from app.ai import vad as vad_mod
from app.ai import asr as asr_mod


@dataclass
class PreparedSpeech:
    speech: np.ndarray        # speech-only waveform (or full audio if VAD found none)
    duration_sec: float
    speech_sec: float


@dataclass
class AudioTranscription:
    transcript: asr_mod.TranscriptResult
    duration_sec: float
    speech_sec: float


def prepare_speech(path: str) -> PreparedSpeech:
    """Load audio and use the full waveform if VAD finds no speech."""
    wav = audio_mod.load_wav_16k(path)
    dur = audio_mod.duration_sec(wav)
    vad_res = vad_mod.extract_speech(wav)
    speech = vad_res.audio if vad_res.speech_sec > 0 else wav
    return PreparedSpeech(speech=speech, duration_sec=dur, speech_sec=vad_res.speech_sec)


def transcribe_audio_file(path: str) -> AudioTranscription:
    prep = prepare_speech(path)
    tr = asr_mod.transcribe(prep.speech)
    # Free Whisper before loading the LLM.
    asr_mod.unload()
    return AudioTranscription(transcript=tr, duration_sec=prep.duration_sec,
                              speech_sec=prep.speech_sec)
