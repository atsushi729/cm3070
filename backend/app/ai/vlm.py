"""Local vision-language model wrapper for photo evaluation."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings

_settings = get_settings()

SYSTEM_PROMPT = (
    "You are a photo-evaluation assistant for a restaurant's social-media "
    "marketing. You are given a photo together with a model-generated "
    "popularity score and objective pixel statistics. Ground every claim in "
    "that evidence — never assert something the data does not support, and "
    "state plainly that the score is a model prediction, not a guarantee of "
    "results. Reply with a single JSON object and nothing else."
)

# Keep the example separate because its JSON braces conflict with str.format().
FEW_SHOT_EXAMPLE = """Example (different photo, for reference only):
Popularity score (0-100, higher is better): 55.0
Pixel attributes: {"brightness": 0.45, "contrast": 0.3, "saturation": 0.5, "sharpness": 0.2}

Good response (describes what the photo actually looks like; never writes the raw numbers themselves):
{
  "strengths": ["The dish is centered with a clean, uncluttered background", "Warm tones make the food look appetizing"],
  "issues": ["The shot looks slightly soft, as if taken without a steady hand or enough light", "A flat overhead angle hides the dish's height and texture"],
  "suggestions": [
    {"priority": 1, "title": "Stabilize the shot or add more light", "reason": "The image has a soft, slightly blurred quality; a tripod or brighter light would let a faster shutter speed keep it crisp"},
    {"priority": 2, "title": "Shoot from an angle instead of straight overhead", "reason": "An angled view reveals layers and texture that a flat top-down shot hides"}
  ]
}
Rule: never write a raw decimal number (like "0.42" or "62.0") anywhere in your strengths, issues, or suggestions — not even in "reason". Describe what the photo looks like in words instead. The score and pixel attributes are evidence for you to reason from, not phrases to copy into your answer.

"""

USER_TEMPLATE = """{score_line}
Pixel attributes: {attributes_json}

Return JSON with exactly these keys:
- "strengths": list of short strings, what the photo does well
- "issues": list of short strings, what could be improved
- "suggestions": list of objects, each with "priority" (int, 1 = highest),
  "title" (short action), and "reason" (why this helps — describe what you
  observe in the photo, in words; do not quote the raw score or attribute
  numbers)
"""


@dataclass
class VlmExplanation:
    strengths: list[str]
    issues: list[str]
    suggestions: list[dict]
    raw: str
    latency_sec: float


@lru_cache(maxsize=1)
def _client():
    from ollama import Client

    return Client(host=_settings.ollama_host)


def build_score_line(score: float | None) -> str:
    """Format the calibrated score for the VLM prompt."""
    if score is not None:
        return f"Popularity score (0-100, higher is better): {score:.1f}"
    # Report missing calibration rather than inventing a score.
    return "Popularity score: not available (model not yet calibrated)"


def build_user_content(score: float | None, attributes: dict) -> str:
    """Build the VLM prompt from an example and measured evidence."""
    return FEW_SHOT_EXAMPLE + USER_TEMPLATE.format(
        score_line=build_score_line(score), attributes_json=json.dumps(attributes)
    )


def parse_explanation_json(raw: str, latency_sec: float) -> VlmExplanation:
    """Parse a JSON explanation, raising ValueError for invalid JSON."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"VLM returned non-JSON: {raw!r}") from exc
    return VlmExplanation(
        strengths=data.get("strengths", []),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        raw=raw,
        latency_sec=latency_sec,
    )


def explanation_to_result_dict(score: float | None, attributes: dict, explanation: VlmExplanation, **extra) -> dict:
    """Convert an explanation to a stored result, merging optional fields."""
    return {
        "calibrated_score": score,
        "attributes": attributes,
        "strengths": explanation.strengths,
        "issues": explanation.issues,
        "suggestions": explanation.suggestions,
        "latency_sec": explanation.latency_sec,
        **extra,
    }


def explain(image_path: str, score: float | None, attributes: dict) -> VlmExplanation:
    """Explain a photo using its score and attributes; evict the VLM afterward."""
    client = _client()
    user_content = build_user_content(score, attributes)
    start = time.perf_counter()
    resp = client.chat(
        model=_settings.vlm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_content,
                "images": [image_path],
            },
        ],
        format="json",
        options={"temperature": 0.0},
        keep_alive=0,
    )
    latency = time.perf_counter() - start
    return parse_explanation_json(resp["message"]["content"], latency)
