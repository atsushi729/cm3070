"""UC2-C popularity evaluation pipeline tests (app/pipelines/uc2_popularity.py).

Popularity model, attribute extractor, and VLM are all mocked — these tests
assert the task's DB status transitions and field writes, mirroring
tests/test_calendar_sync.py's SessionLocal-patching pattern.
"""
from __future__ import annotations

import pytest
from PIL import Image

from app.ai import popularity, vlm
from app.models import ImageEvaluation, ImageEvaluationStatus
from app.pipelines import uc2_popularity
from app.services import attributes


def _seed_evaluation(Session, tmp_path) -> int:
    img_path = tmp_path / "photo.jpg"
    Image.new("RGB", (16, 16), (200, 100, 50)).save(img_path)

    s = Session()
    ev = ImageEvaluation(storage_path=str(img_path))
    s.add(ev)
    s.commit()
    ev_id = ev.id
    s.close()
    return ev_id


def _get(Session, ev_id) -> ImageEvaluation:
    s = Session()
    try:
        return s.get(ImageEvaluation, ev_id)
    finally:
        s.close()


def test_evaluate_image_success_populates_all_fields(Session, monkeypatch, tmp_path):
    monkeypatch.setattr(uc2_popularity, "SessionLocal", Session)
    monkeypatch.setattr(popularity, "score", lambda image: 0.7)
    monkeypatch.setattr(popularity, "calibrate", lambda raw: 70.0)
    monkeypatch.setattr(attributes, "extract", lambda image: {"brightness": 0.5})
    monkeypatch.setattr(
        vlm, "explain",
        lambda path, score, attrs: vlm.VlmExplanation(
            strengths=["clear subject"], issues=["small subject"],
            suggestions=[{"priority": 1, "title": "crop", "reason": "why"}],
            raw="{}", latency_sec=0.1,
        ),
    )
    ev_id = _seed_evaluation(Session, tmp_path)

    out = uc2_popularity.evaluate_image.run(ev_id)

    assert out["status"] == "completed"
    ev = _get(Session, ev_id)
    assert ev.status == ImageEvaluationStatus.completed
    assert ev.popularity_score_raw == 0.7
    assert ev.popularity_score == 70.0
    assert ev.attributes_json == {"brightness": 0.5}
    assert ev.strengths_json == ["clear subject"]
    assert ev.suggestions_json[0]["title"] == "crop"
    assert ev.vlm_error is None
    assert ev.finished_at is not None


def test_evaluate_image_uncalibrated_score_stays_none(Session, monkeypatch, tmp_path):
    # calibrate() returns None while the model is uncalibrated; the pipeline
    # must keep the raw score, store no fake 0-100 value, pass None through to
    # the VLM, and still complete.
    monkeypatch.setattr(uc2_popularity, "SessionLocal", Session)
    monkeypatch.setattr(popularity, "score", lambda image: -1.844)
    monkeypatch.setattr(popularity, "calibrate", lambda raw: None)
    monkeypatch.setattr(attributes, "extract", lambda image: {"brightness": 0.5})

    seen_scores: list = []

    def _explain(path, score, attrs):
        seen_scores.append(score)
        return vlm.VlmExplanation(
            strengths=["s"], issues=[], suggestions=[], raw="{}", latency_sec=0.1,
        )

    monkeypatch.setattr(vlm, "explain", _explain)
    ev_id = _seed_evaluation(Session, tmp_path)

    out = uc2_popularity.evaluate_image.run(ev_id)

    assert out["status"] == "completed"
    ev = _get(Session, ev_id)
    assert ev.popularity_score_raw == -1.844
    assert ev.popularity_score is None
    assert seen_scores == [None]


def test_evaluate_image_vlm_failure_degrades_to_partial(Session, monkeypatch, tmp_path):
    monkeypatch.setattr(uc2_popularity, "SessionLocal", Session)
    monkeypatch.setattr(popularity, "score", lambda image: 0.3)
    monkeypatch.setattr(popularity, "calibrate", lambda raw: 30.0)
    monkeypatch.setattr(attributes, "extract", lambda image: {"brightness": 0.2})

    def _boom(path, score, attrs):
        raise ValueError("VLM returned non-JSON")

    monkeypatch.setattr(vlm, "explain", _boom)
    ev_id = _seed_evaluation(Session, tmp_path)

    out = uc2_popularity.evaluate_image.run(ev_id)

    assert out["status"] == "completed_partial"
    ev = _get(Session, ev_id)
    assert ev.status == ImageEvaluationStatus.completed_partial
    assert ev.popularity_score == 30.0  # score/attributes preserved despite VLM failure
    assert "non-JSON" in ev.vlm_error


def test_evaluate_image_popularity_failure_marks_failed(Session, monkeypatch, tmp_path):
    monkeypatch.setattr(uc2_popularity, "SessionLocal", Session)

    def _boom(image):
        raise RuntimeError("model weights not found")

    monkeypatch.setattr(popularity, "score", _boom)
    ev_id = _seed_evaluation(Session, tmp_path)

    with pytest.raises(RuntimeError):
        uc2_popularity.evaluate_image.run(ev_id)

    ev = _get(Session, ev_id)
    assert ev.status == ImageEvaluationStatus.failed
    assert "model weights not found" in ev.error
