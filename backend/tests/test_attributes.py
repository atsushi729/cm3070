"""Attribute extractor tests (app/services/attributes.py).

Uses synthetic PIL images (solid colors, sharp vs. blurred checkerboards) so
the tests are deterministic and need no external test-image files.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from app.services import attributes


def _checkerboard(size: int = 64, cell: int = 8) -> Image.Image:
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    for y in range(0, size, cell * 2):
        for x in range(0, size, cell * 2):
            draw.rectangle([x, y, x + cell, y + cell], fill="black")
            draw.rectangle(
                [x + cell, y + cell, x + cell * 2, y + cell * 2], fill="black"
            )
    return img


def test_bright_image_has_higher_brightness_than_dark():
    bright = Image.new("RGB", (32, 32), (250, 250, 250))
    dark = Image.new("RGB", (32, 32), (10, 10, 10))

    assert attributes.extract(bright)["brightness"] > attributes.extract(dark)["brightness"]


def test_saturated_image_has_higher_saturation_than_grey():
    saturated = Image.new("RGB", (32, 32), (255, 0, 0))
    grey = Image.new("RGB", (32, 32), (128, 128, 128))

    assert attributes.extract(saturated)["saturation"] > attributes.extract(grey)["saturation"]


def test_blurring_reduces_sharpness():
    sharp = _checkerboard()
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=4))

    assert attributes.extract(sharp)["sharpness"] > attributes.extract(blurred)["sharpness"]


def test_all_attributes_are_in_expected_range():
    attrs = attributes.extract(_checkerboard())

    for key in ("brightness", "contrast", "saturation", "sharpness"):
        assert 0.0 <= attrs[key] <= 1.0, f"{key}={attrs[key]} out of range"
