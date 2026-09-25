"""Shared test fixtures.

Tests run against an in-memory SQLite database (StaticPool so the one connection
is shared) — no Postgres/Redis needed. The ORM models use portable column types,
so create_all works on SQLite for these unit tests.
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register tables on Base.metadata
from app.db import Base
from app.models import BookingStatus, Reservation, ReviewStatus


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(Session):
    s = Session()
    try:
        yield s
    finally:
        s.close()


def make_reservation(
    *,
    name: str | None = "Tanaka",
    res_date: date | None = date(2026, 6, 20),
    res_time: time | None = time(19, 30),
    party: int | None = 2,
    review_status: ReviewStatus = ReviewStatus.pending,
    booking_status: BookingStatus = BookingStatus.draft,
) -> Reservation:
    return Reservation(
        ai_name=name,
        ai_date=res_date,
        ai_time=res_time,
        ai_party_size=party,
        name=name,
        reservation_date=res_date,
        reservation_time=res_time,
        party_size=party,
        review_status=review_status,
        booking_status=booking_status,
    )
