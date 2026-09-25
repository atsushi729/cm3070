"""ASR wrapper tests using a fake model."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np

from app.ai import asr


class _FakeSegment:
    def __init__(self, text: str):
        self.text = text


class _FakeModel:
    def __init__(self):
        self.calls: list[dict] = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        return [_FakeSegment("こんにちは")], SimpleNamespace(language="ja")


def test_load_model_prefers_bootstrapped_small_model(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def fake_whisper_model(model_source, **kwargs):
        captured["model_source"] = model_source
        captured.update(kwargs)
        return object()

    (tmp_path / "model.bin").touch()
    monkeypatch.setattr(asr, "_LOCAL_SMALL_MODEL", tmp_path)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=fake_whisper_model),
    )
    asr._load_model.cache_clear()
    try:
        asr._load_model("small")
    finally:
        asr._load_model.cache_clear()

    assert captured["model_source"] == str(tmp_path)
    assert captured["device"] == "cpu"


def test_transcribe_passes_surname_hotwords_to_model(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(asr, "_load_model", lambda model_size=None: fake)

    asr.transcribe(np.zeros(16000, dtype=np.float32))

    assert len(fake.calls) == 1
    hotwords = fake.calls[0].get("hotwords")
    assert hotwords, "hotwords bias was not passed to faster-whisper"
    assert "佐藤" in hotwords
    assert "田中" in hotwords


def test_transcribe_still_returns_joined_text_and_language(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(asr, "_load_model", lambda model_size=None: fake)

    result = asr.transcribe(np.zeros(16000, dtype=np.float32))

    assert result.text == "こんにちは"
    assert result.language == "ja"
