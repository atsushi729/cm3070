"""Pretrained image-popularity model wrapper (UC2-C).

Ding et al., "Intrinsic Image Popularity Assessment" (arXiv:1907.01985) — a
ResNet50 trained on Instagram popularity-discriminable image pairs, released
pretrained at https://github.com/dingkeyan93/Intrinsic-Image-Popularity.
Used for inference only: no fine-tuning, no dataset to collect. The model is
lazy-loaded and cached for subsequent evaluations.

"""
from __future__ import annotations

from functools import lru_cache

from PIL import Image

from app.config import get_settings

_settings = get_settings()


@lru_cache(maxsize=1)
def _load_model():
    import torch
    import torchvision.models as models

    net = models.resnet50()
    net.fc = torch.nn.Linear(in_features=2048, out_features=1)
    # Restrict third-party checkpoint loading to tensor data.
    state_dict = torch.load(
        _settings.popularity_model_path, map_location="cpu", weights_only=True
    )
    net.load_state_dict(state_dict)
    net.eval()
    return net


def score(image: Image.Image) -> float:
    """Raw popularity-model output for a single PIL image (uncalibrated)."""
    import torch
    import torchvision.transforms as transforms

    net = _load_model()
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])
    tensor = transform(image.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        return net(tensor).item()


def calibrate(raw_score: float) -> float | None:
    """Map a raw score onto 0-100 using settings.popularity_score_min/max,
    clipped to that range. Returns None while uncalibrated (min >= max, the
    unconfigured sentinel): raw model output is not a 0-100 quantity (measured
    values are e.g. -1.844), so any number derived from a degenerate range
    would be a fabricated score rather than a calibrated one."""
    lo, hi = _settings.popularity_score_min, _settings.popularity_score_max
    if hi <= lo:
        return None
    pct = (raw_score - lo) / (hi - lo) * 100
    return max(0.0, min(100.0, pct))
