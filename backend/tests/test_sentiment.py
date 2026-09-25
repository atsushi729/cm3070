"""Unit tests for UC2 sentiment and its training data loader."""
from __future__ import annotations

from app.config import get_settings
from app.ai import sentiment


def test_config_exposes_sentiment_defaults():
    s = get_settings()
    assert s.sentiment_model_path == "./data/models/sentiment-mbert"
    assert s.sentiment_finetune_base == "bert-base-multilingual-cased"
    assert s.sentiment_baseline_model  # non-empty HF id for the zero-shot baseline


def test_labels_order_is_canonical():
    assert sentiment.LABELS == ("negative", "neutral", "positive")


def test_canonical_label_maps_aliases():
    assert sentiment.canonical_label("POSITIVE") == "positive"
    assert sentiment.canonical_label("neg") == "negative"
    assert sentiment.canonical_label("LABEL_1") == "neutral"
    assert sentiment.canonical_label("5 stars") == "positive"
    assert sentiment.canonical_label("garbage") is None


def test_analyze_sentiment_returns_result(monkeypatch):
    monkeypatch.setattr(sentiment, "_build_classifier",
                        lambda model_path: (lambda t: ("positive", 0.97)))
    sentiment.unload()  # ensure cache is empty so the fake build is used
    r = sentiment.analyze_sentiment("料理も接客も最高でした")
    assert r.label == "positive"
    assert r.score == 0.97
    assert r.latency_sec >= 0.0


def test_analyze_sentiment_empty_text_is_none():
    r = sentiment.analyze_sentiment("   ")
    assert r.label is None
    assert r.score is None


def test_unload_clears_classifier_cache(monkeypatch):
    monkeypatch.setattr(sentiment, "_build_classifier",
                        lambda model_path: (lambda t: ("neutral", 0.5)))
    sentiment.unload()
    sentiment._load_classifier("dummy-path")  # populate the cache
    assert sentiment._load_classifier.cache_info().currsize == 1
    sentiment.unload()
    assert sentiment._load_classifier.cache_info().currsize == 0


import importlib

import json as _json

train_mod = importlib.import_module("scripts.train_sentiment")


def test_read_split_encodes_labels_to_ids(tmp_path):
    p = tmp_path / "mini.json"
    p.write_text(_json.dumps({
        "items": [
            {"id": "s1", "lang": "en", "text": "the food was delicious", "label": "positive"},
            {"id": "s2", "lang": "ja", "text": "二度と行きません", "label": "negative"},
        ]
    }, ensure_ascii=False))
    texts, ids = train_mod.read_split(p)
    assert texts == ["the food was delicious", "二度と行きません"]
    assert ids == [sentiment.LABELS.index("positive"), sentiment.LABELS.index("negative")]
