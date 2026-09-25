"""Extract reservation fields from Japanese or English transcripts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta

from app.ai import llm as llm_mod

SYSTEM_PROMPT = (
    "You are a reservation-desk assistant for a Japanese restaurant. "
    "You extract booking details from a transcribed phone call. "
    "The call may be in Japanese or English. "
    "Reply with a single JSON object and nothing else."
)

USER_TEMPLATE = """Today is {today} ({weekday}). The current time is {now_time}.
Extract the reservation from this call transcript.

Return JSON with exactly these keys:
- "name": the customer's name EXACTLY as spoken in the transcript, in its
  original script (do not translate or romanise Japanese names), or null
- "date_phrase": ONLY the date word(s), copied verbatim in the language the
  caller used — e.g. "tomorrow", "this coming Friday", "明日", "今週末".
  Rules: (1) do not translate or convert numerals to another script;
  (2) do not include time-of-day words like "evening"/"夜" in this field —
  those belong in "time"; (3) if the caller said "today"/"now"/"今日" or
  otherwise implied same-day, still copy that word here — do not return null
  just because the date is today; (4) return null only if the caller
  mentioned no day or date at all
- "time": the reservation time as "HH:MM" 24-hour, or null
- "party_size": integer number of guests, or null
- "confidence": your confidence 0.0-1.0 that the extraction is correct

Transcript:
\"\"\"{transcript}\"\"\"
"""

_JA_WEEKDAY_TO_INT = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
_EN_WEEKDAY_TO_INT = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_EN_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_JA_KANJI_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_FIXED_DAY_OFFSETS = {
    "今日": 0, "today": 0,
    "明日": 1, "tomorrow": 1,
    "明後日": 2, "the day after tomorrow": 2,
}


def _normalize_phrase(phrase: str) -> str:
    """Strip noise the LLM adds despite the "copy verbatim" instruction:
    a trailing time-of-day word (明日の夜 -> 明日) or a bare dangling
    particle (3日後の -> 3日後)."""
    p = phrase.strip()
    p = re.sub(r"(の(夜|夕方|朝|昼|午前|午後)|[の、,])\s*$", "", p)
    return p.strip()


def _match_day_offset(pattern: str, s: str, word_table: dict[str, int]) -> int | None:
    """Match `pattern` (a "<number> <unit>" style phrase) against s and
    resolve the captured number, digit or word, via word_table."""
    m = re.fullmatch(pattern, s)
    if not m:
        return None
    raw = m.group(1)
    return int(raw) if raw.isdigit() else word_table.get(raw)


@dataclass
class ExtractedFields:
    name: str | None
    date: date | None
    time: time | None
    party_size: int | None
    confidence: float | None
    raw: str
    latency_sec: float


def _next_weekday(ref: date, target_wd: int) -> date:
    """Next occurrence of target_wd strictly after ref (1..7 days ahead).

    Follows the evaluation-set convention: "this weekend" /
    "this coming <weekday>" never resolves to today, even if today is that
    weekday.
    """
    days = (target_wd - ref.weekday()) % 7
    return ref + timedelta(days=days or 7)


def _resolve_date_phrase(phrase: str | None, now: datetime) -> date | None:
    """Resolve the LLM's raw date phrase deterministically."""
    if not phrase or not phrase.strip():
        return None
    p = _normalize_phrase(phrase)
    p_lower = p.lower()
    today = now.date()

    if p_lower in _FIXED_DAY_OFFSETS:
        return today + timedelta(days=_FIXED_DAY_OFFSETS[p_lower])
    if p_lower in ("今週末", "this weekend"):
        return _next_weekday(today, 5)  # Saturday

    n = _match_day_offset(r"(\d+|[一二三四五六七八九十]+)\s*日後", p, _JA_KANJI_DIGITS)
    if n is not None:
        return today + timedelta(days=n)
    n = _match_day_offset(r"in (\d+|[a-z]+) days?", p_lower, _EN_NUMBER_WORDS)
    if n is not None:
        return today + timedelta(days=n)

    # Match any weekday mention; this domain treats it as the next occurrence.
    m = re.search(r"([月火水木金土日])曜日", p)
    if m:
        return _next_weekday(today, _JA_WEEKDAY_TO_INT[m.group(1)])
    for name, wd in _EN_WEEKDAY_TO_INT.items():
        if re.search(rf"\b{name}\b", p_lower):
            return _next_weekday(today, wd)

    return None


def _parse_time(v) -> time | None:
    if not v:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(str(v), fmt).time()
        except ValueError:
            continue
    return None


def _parse_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def extract_reservation(
    transcript: str,
    *,
    now: datetime | None = None,
    model: str | None = None,
    keep_alive: str | int = 0,
) -> ExtractedFields:
    now = now or datetime.now()
    prompt = USER_TEMPLATE.format(
        today=now.strftime("%Y-%m-%d"),
        weekday=now.strftime("%A"),
        now_time=now.strftime("%H:%M"),
        transcript=transcript.strip(),
    )
    res = llm_mod.generate_json(SYSTEM_PROMPT, prompt, model=model, keep_alive=keep_alive)
    d = res.data
    name = d.get("name")
    return ExtractedFields(
        name=str(name).strip() if name else None,
        date=_resolve_date_phrase(d.get("date_phrase"), now),
        time=_parse_time(d.get("time")),
        party_size=_parse_int(d.get("party_size")),
        confidence=(float(d["confidence"]) if isinstance(d.get("confidence"), (int, float)) else None),
        raw=res.raw,
        latency_sec=res.latency_sec,
    )
