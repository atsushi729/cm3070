"""Popularity model wrapper tests with a fake model."""
from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from app.ai import popularity


class _FakeNet:
    def __init__(self, value: float):
        self.value = value
        self.calls = 0

    def __call__(self, tensor):
        self.calls += 1
        return SimpleNamespace(item=lambda: self.value)


def test_score_returns_raw_model_output(monkeypatch):
    fake = _FakeNet(0.42)
    monkeypatch.setattr(popularity, "_load_model", lambda: fake)
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))

    result = popularity.score(img)

    assert result == 0.42
    assert fake.calls == 1


def test_calibrate_scales_to_0_100(monkeypatch):
    monkeypatch.setattr(popularity._settings, "popularity_score_min", 0.0)
    monkeypatch.setattr(popularity._settings, "popularity_score_max", 1.0)

    assert popularity.calibrate(0.5) == 50.0


def test_calibrate_clips_out_of_range_values(monkeypatch):
    monkeypatch.setattr(popularity._settings, "popularity_score_min", 0.0)
    monkeypatch.setattr(popularity._settings, "popularity_score_max", 1.0)

    assert popularity.calibrate(-1.0) == 0.0
    assert popularity.calibrate(2.0) == 100.0


def test_calibrate_returns_none_when_uncalibrated(monkeypatch):
    # min == max is the "not calibrated" sentinel. Raw model output is NOT a
    # 0-100 value (measured raw scores are e.g. -1.844), so passing it through
    # or clipping it would show a meaningless number to the user — the only
    # honest answer is "no calibrated score".
    monkeypatch.setattr(popularity._settings, "popularity_score_min", 5.0)
    monkeypatch.setattr(popularity._settings, "popularity_score_max", 5.0)

    assert popularity.calibrate(3.0) is None


def test_calibrate_returns_none_when_range_inverted(monkeypatch):
    monkeypatch.setattr(popularity._settings, "popularity_score_min", 2.0)
    monkeypatch.setattr(popularity._settings, "popularity_score_max", -2.0)

    assert popularity.calibrate(0.5) is None
