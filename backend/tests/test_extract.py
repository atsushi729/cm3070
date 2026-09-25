"""UC1 entity extraction tests (app/ai/extract.py).

The relative-date resolver is a pure function tested directly (no LLM), plus
one integration-style test that mocks the LLM boundary (app.ai.llm.generate_json)
to confirm extract_reservation() wires the LLM's raw date_phrase through the
resolver correctly.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.ai import extract
from app.ai import llm

_NOW = datetime(2026, 6, 13, 12, 0)


@pytest.mark.parametrize(
    "phrase, expected",
    [
        # Japanese
        ("今日", date(2026, 6, 13)),
        ("明日", date(2026, 6, 14)),
        ("明後日", date(2026, 6, 15)),
        ("3日後", date(2026, 6, 16)),
        ("今週末", date(2026, 6, 20)),  # ref is already Saturday -> next Saturday
        ("今度の金曜日", date(2026, 6, 19)),
        ("今度の日曜日", date(2026, 6, 14)),
        # English
        ("today", date(2026, 6, 13)),
        ("tomorrow", date(2026, 6, 14)),
        ("the day after tomorrow", date(2026, 6, 15)),
        ("in three days", date(2026, 6, 16)),
        ("this weekend", date(2026, 6, 20)),
        ("this coming Friday", date(2026, 6, 19)),
        ("this coming Sunday", date(2026, 6, 14)),
    ],
)
def test_resolve_date_phrase(phrase, expected):
    assert extract._resolve_date_phrase(phrase, _NOW) == expected


@pytest.mark.parametrize("phrase", [None, "", "   ", "next century", "whenever works"])
def test_resolve_date_phrase_unrecognised_returns_none(phrase):
    assert extract._resolve_date_phrase(phrase, _NOW) is None


@pytest.mark.parametrize(
    "phrase, expected",
    [
        # Date phrases may include time-of-day words.
        ("明日の夜", date(2026, 6, 14)),
        ("3日後の夜", date(2026, 6, 16)),
        ("3日後の夕方", date(2026, 6, 16)),
        ("3日後の", date(2026, 6, 16)),  # trailing bare particle, no suffix word
        # Day offsets may use kanji numerals.
        ("三日後", date(2026, 6, 16)),
        ("二日後", date(2026, 6, 15)),
        # Resolve weekday names despite varied prefixes or mixed language.
        ("来週日曜日", date(2026, 6, 14)),
        ("来週の金曜日", date(2026, 6, 19)),
        ("今週金曜日", date(2026, 6, 19)),
        ("次週日曜日", date(2026, 6, 14)),
        ("この Coming Friday", date(2026, 6, 19)),
        ("この Coming 金曜日", date(2026, 6, 19)),
    ],
)
def test_resolve_date_phrase_tolerates_llm_paraphrase(phrase, expected):
    assert extract._resolve_date_phrase(phrase, _NOW) == expected


def test_extract_reservation_resolves_date_phrase_via_llm(monkeypatch):
    """Resolve the LLM's raw date phrase rather than accepting a computed date."""

    def fake_generate_json(system, prompt, *, temperature=0.0, keep_alive=0, model=None):
        return llm.LlmJsonResult(
            data={
                "name": "田中",
                "date_phrase": "明日",
                "time": "19:00",
                "party_size": 2,
                "confidence": 0.95,
            },
            raw='{"name": "田中"}',
            latency_sec=0.01,
        )

    monkeypatch.setattr(llm, "generate_json", fake_generate_json)

    fields = extract.extract_reservation("dummy transcript", now=_NOW)

    assert fields.date == date(2026, 6, 14)
    assert fields.name == "田中"
    assert fields.time == datetime(2026, 6, 13, 19, 0).time()
    assert fields.party_size == 2
