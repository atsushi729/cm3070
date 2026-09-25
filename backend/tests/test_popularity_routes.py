"""UC2-C image evaluation route tests. Builds a minimal FastAPI app around
just the popularity router, avoiding app.main's lifespan (matches the
pattern used for UC1's /recordings and, historically, UC2-B's routes).
"""
from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

import app.api.popularity_routes as routes_mod
from app.db import get_db
from app.models import ImageEvaluation, ImageEvaluationStatus
from app.pipelines import uc2_popularity


def _make_client(Session) -> TestClient:
    app = FastAPI()
    app.include_router(routes_mod.router)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _fake_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (100, 150, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def test_evaluate_accepts_image_creates_row_and_enqueues_task(Session, monkeypatch, tmp_path):
    monkeypatch.setattr(routes_mod, "_IMAGE_DIR", tmp_path)
    enqueued: list[int] = []
    monkeypatch.setattr(uc2_popularity.evaluate_image, "delay", lambda ev_id: enqueued.append(ev_id))
    client = _make_client(Session)

    resp = client.post(
        "/api/uc2/images/evaluate",
        files={"file": ("photo.jpg", _fake_jpeg_bytes(), "image/jpeg")},
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "uploaded"
    assert enqueued == [body["id"]]


def test_evaluate_rejects_non_image_content_type(Session, monkeypatch, tmp_path):
    monkeypatch.setattr(routes_mod, "_IMAGE_DIR", tmp_path)
    client = _make_client(Session)

    resp = client.post(
        "/api/uc2/images/evaluate",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert resp.status_code == 400


def test_get_evaluation_returns_seeded_row(Session):
    s = Session()
    ev = ImageEvaluation(
        storage_path="/tmp/x.jpg",
        status=ImageEvaluationStatus.completed,
        popularity_score=70.0,
    )
    s.add(ev)
    s.commit()
    ev_id = ev.id
    s.close()
    client = _make_client(Session)

    resp = client.get(f"/api/uc2/images/evaluate/{ev_id}")

    assert resp.status_code == 200
    assert resp.json()["popularity_score"] == 70.0


def test_get_evaluation_404_when_missing(Session):
    client = _make_client(Session)

    resp = client.get("/api/uc2/images/evaluate/999")

    assert resp.status_code == 404
