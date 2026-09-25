"""Measure brightness, contrast, saturation, and sharpness with OpenCV."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def extract(image: Image.Image) -> dict[str, float]:
    """Return brightness/contrast/saturation/sharpness, each in [0, 1]."""
    rgb = np.array(image.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    brightness = float(np.mean(hsv[:, :, 2])) / 255.0
    contrast = float(np.std(gray)) / 255.0
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0
    # Laplacian variance is a standard blur-detection heuristic (higher =
    # sharper). Divide by a fixed constant to squash typical sharp-photo
    # values toward [0, 1]; extreme outliers are clipped, not left unbounded.
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness = min(1.0, laplacian_var / 1000.0)

    return {
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "saturation": round(saturation, 4),
        "sharpness": round(sharpness, 4),
    }
