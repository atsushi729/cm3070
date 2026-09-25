"""Local Ollama client for structured entity extraction."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings

_settings = get_settings()


@dataclass
class LlmJsonResult:
    data: dict
    raw: str
    latency_sec: float


@lru_cache(maxsize=1)
def _client():
    from ollama import Client

    return Client(host=_settings.ollama_host)


def generate_json(
    system: str,
    prompt: str,
    *,
    temperature: float = 0.0,
    keep_alive: str | int = 0,
    model: str | None = None,
) -> LlmJsonResult:
    """Call Ollama in JSON mode; evict the model when keep_alive is zero."""
    client = _client()
    start = time.perf_counter()
    resp = client.chat(
        model=model or _settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"temperature": temperature},
        keep_alive=keep_alive,
    )
    latency = time.perf_counter() - start
    raw = resp["message"]["content"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON: {raw!r}") from exc
    return LlmJsonResult(data=data, raw=raw, latency_sec=latency)


def health() -> bool:
    """True if the configured model is available on the Ollama host."""
    try:
        models = _client().list().get("models", [])
        names = {m.get("model") or m.get("name") for m in models}
        return _settings.llm_model in names
    except Exception:
        return False
