"""Settings status route tests. Builds a minimal FastAPI app around just the
settings router, avoiding app.main's lifespan (which would run create_all
against the real Postgres-configured settings.database_url).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.settings_routes import router as settings_router
from app.db import get_db
from app.services import calendar


def _make_client(Session) -> TestClient:
    app = FastAPI()
    app.include_router(settings_router)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_status_reports_db_ok_and_integrations_off(Session, monkeypatch):
    monkeypatch.setattr(calendar, "is_enabled", lambda: False)
    client = _make_client(Session)

    resp = client.get("/api/settings/status")

    assert resp.status_code == 200
    assert resp.json() == {
        "db": True,
        "calendar_sync_enabled": False,
    }


def test_status_reports_calendar_enabled(Session, monkeypatch):
    monkeypatch.setattr(calendar, "is_enabled", lambda: True)
    client = _make_client(Session)

    resp = client.get("/api/settings/status")

    body = resp.json()
    assert body["calendar_sync_enabled"] is True
