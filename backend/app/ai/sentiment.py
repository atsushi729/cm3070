"""Multilingual (JA/EN) sentiment classifier for UC2 marketing analytics.

The model path is relative to backend/.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from app.config import get_settings

_settings = get_settings()

# Canonical classes; the tuple index is the class id used during fine-tuning.
LABELS: tuple[str, str, str] = ("negative", "neutral", "positive")

# Map any model's raw label/alias to a canonical label. Covers our fine-tuned
# model (returns the canonical strings), transformers' default LABEL_<id>, the
# baseline's pos/neu/neg, and star-rating models (1-2*=neg, 3*=neu, 4-5*=pos).
_ALIASES: dict[str, str] = {
    "negative": "negative", "neg": "negative", "label_0": "negative",
    "1 star": "negative", "2 stars": "negative",
    "neutral": "neutral", "neu": "neutral", "label_1": "neutral", "3 stars": "neutral",
    "positive": "positive", "pos": "positive", "label_2": "positive",
    "4 stars": "positive", "5 stars": "positive",
}


def canonical_label(raw: str) -> str | None:
    """Normalise a model's raw label to one of LABELS, or None if unknown."""
    return _ALIASES.get(str(raw).strip().lower())


@dataclass
class SentimentResult:
    label: str | None    # one of LABELS, or None for empty input
    score: float | None  # softmax confidence of the chosen class
    latency_sec: float


def _build_classifier(model_path: str) -> Callable[[str], tuple[str, float]]:
    """Build a text -> (canonical_label, score) callable from a saved model.

    Heavy (loads the transformer); isolated here so tests can monkeypatch it
    and the lru_cache wrapper stays trivially testable.
    """
    from transformers import pipeline

    pipe = pipeline(
        "text-classification",
        model=model_path,
        tokenizer=model_path,
        truncation=True,
        max_length=128,
    )

    def classify(text: str) -> tuple[str, float]:
        out = pipe(text)[0]
        label = canonical_label(out["label"]) or out["label"]
        return label, float(out["score"])

    return classify


@lru_cache(maxsize=1)
def _load_classifier(model_path: str) -> Callable[[str], tuple[str, float]]:
    return _build_classifier(model_path)


def analyze_sentiment(text: str, *, model_path: str | None = None) -> SentimentResult:
    """Classify a review's overall sentiment. Empty/whitespace -> label None."""
    if not text or not text.strip():
        return SentimentResult(label=None, score=None, latency_sec=0.0)
    classify = _load_classifier(model_path or _settings.sentiment_model_path)
    start = time.perf_counter()
    label, score = classify(text)
    return SentimentResult(label=label, score=score, latency_sec=time.perf_counter() - start)


def unload() -> None:
    """Free the sentiment model from this process's RAM (residency rule)."""
    import gc

    _load_classifier.cache_clear()
    gc.collect()
