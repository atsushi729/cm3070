"""VLM wrapper tests using a fake Ollama client."""
from __future__ import annotations

import json

import pytest

from app.ai import vlm


class _FakeClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": json.dumps(self.response)}}


class _BadJsonClient:
    def chat(self, **kwargs):
        return {"message": {"content": "not json"}}


def test_explain_passes_image_and_structured_evidence(monkeypatch):
    fake = _FakeClient({
        "strengths": ["clear subject"],
        "issues": ["cluttered background"],
        "suggestions": [{"priority": 1, "title": "crop tighter", "reason": "subject is small"}],
    })
    monkeypatch.setattr(vlm, "_client", lambda: fake)

    result = vlm.explain("/tmp/photo.jpg", 62.0, {"brightness": 0.44})

    assert result.strengths == ["clear subject"]
    assert result.issues == ["cluttered background"]
    assert result.suggestions[0]["title"] == "crop tighter"

    call = fake.calls[0]
    assert call["keep_alive"] == 0
    user_message = call["messages"][1]
    assert user_message["images"] == ["/tmp/photo.jpg"]
    assert "62.0" in user_message["content"]
    assert "brightness" in user_message["content"]


def test_explain_handles_missing_score(monkeypatch):
    # When the popularity model is uncalibrated, calibrate() yields None; the
    # VLM must still run, told plainly that no score is available, so the
    # explanation leans on the pixel attributes instead of a fabricated number.
    fake = _FakeClient({"strengths": [], "issues": [], "suggestions": []})
    monkeypatch.setattr(vlm, "_client", lambda: fake)

    result = vlm.explain("/tmp/photo.jpg", None, {"brightness": 0.44})

    assert result.strengths == []
    user_content = fake.calls[0]["messages"][1]["content"]
    assert "not available" in user_content
    assert "None" not in user_content
    assert "brightness" in user_content


def test_explain_raises_valueerror_on_non_json_response(monkeypatch):
    monkeypatch.setattr(vlm, "_client", lambda: _BadJsonClient())

    with pytest.raises(ValueError):
        vlm.explain("/tmp/photo.jpg", 50.0, {})


def test_build_score_line_with_score():
    assert vlm.build_score_line(62.0) == "Popularity score (0-100, higher is better): 62.0"


def test_build_score_line_without_score():
    line = vlm.build_score_line(None)
    assert "not available" in line
    assert "None" not in line


def test_build_user_content_includes_few_shot_before_real_evidence():
    content = vlm.build_user_content(62.0, {"brightness": 0.5})

    example_pos = content.find("Example (different photo")
    real_pos = content.find("Popularity score (0-100")
    assert example_pos != -1
    assert 0 <= example_pos < real_pos
    assert "62.0" in content
    assert "brightness" in content


def test_parse_explanation_json_extracts_fields():
    raw = json.dumps({
        "strengths": ["a"],
        "issues": ["b"],
        "suggestions": [{"priority": 1, "title": "t", "reason": "r"}],
    })

    result = vlm.parse_explanation_json(raw, latency_sec=1.5)

    assert result.strengths == ["a"]
    assert result.issues == ["b"]
    assert result.suggestions[0]["title"] == "t"
    assert result.raw == raw
    assert result.latency_sec == 1.5


def test_parse_explanation_json_defaults_missing_keys():
    result = vlm.parse_explanation_json("{}", latency_sec=0.0)

    assert result.strengths == []
    assert result.issues == []
    assert result.suggestions == []


def test_parse_explanation_json_raises_on_non_json():
    with pytest.raises(ValueError):
        vlm.parse_explanation_json("not json", latency_sec=0.0)


def test_explain_includes_few_shot_example_before_real_evidence(monkeypatch):
    fake = _FakeClient({"strengths": [], "issues": [], "suggestions": []})
    monkeypatch.setattr(vlm, "_client", lambda: fake)

    vlm.explain("/tmp/photo.jpg", 50.0, {"brightness": 0.5})

    user_content = fake.calls[0]["messages"][1]["content"]
    assert "never write a raw decimal number" in user_content
    example_pos = user_content.find("Example (different photo")
    real_pos = user_content.find("Popularity score (0-100")
    assert example_pos != -1
    assert 0 <= example_pos < real_pos


def test_user_template_instructs_against_quoting_raw_numbers():
    assert "do not quote the raw score or attribute" in vlm.USER_TEMPLATE


def test_explanation_to_result_dict_has_shared_shape():
    explanation = vlm.VlmExplanation(
        strengths=["a"], issues=["b"], suggestions=[{"priority": 1, "title": "t", "reason": "r"}],
        raw="{}", latency_sec=1.5,
    )

    result = vlm.explanation_to_result_dict(62.0, {"brightness": 0.5}, explanation)

    assert result == {
        "calibrated_score": 62.0,
        "attributes": {"brightness": 0.5},
        "strengths": ["a"],
        "issues": ["b"],
        "suggestions": [{"priority": 1, "title": "t", "reason": "r"}],
        "latency_sec": 1.5,
    }


def test_explanation_to_result_dict_merges_extra_fields():
    explanation = vlm.VlmExplanation(
        strengths=[], issues=[], suggestions=[], raw="{}", latency_sec=0.1,
    )

    result = vlm.explanation_to_result_dict(
        None, {}, explanation, usage={"prompt_tokens": 10, "completion_tokens": 5}
    )

    assert result["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert result["calibrated_score"] is None
