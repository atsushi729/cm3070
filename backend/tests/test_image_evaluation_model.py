"""ImageEvaluation model tests (app/models.py) — table creates and round-trips."""
from __future__ import annotations

from app.models import ImageEvaluation, ImageEvaluationStatus


def test_image_evaluation_round_trips_through_db(Session):
    s = Session()
    ev = ImageEvaluation(storage_path="/tmp/photo.jpg")
    s.add(ev)
    s.commit()
    ev_id = ev.id
    s.close()

    s2 = Session()
    fetched = s2.get(ImageEvaluation, ev_id)
    s2.close()

    assert fetched.storage_path == "/tmp/photo.jpg"
    assert fetched.status == ImageEvaluationStatus.uploaded
    assert fetched.popularity_score is None
    assert fetched.attributes_json is None
