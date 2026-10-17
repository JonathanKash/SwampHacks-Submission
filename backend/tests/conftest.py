"""Shared fixtures: a deterministic synthetic 'photo' and image-data loading without CLIP."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lineage.plugins.image_fingerprint import phash  # noqa: E402
from lineage.types import ImageData  # noqa: E402


def synthetic_photo(seed: int = 1, size: tuple[int, int] = (480, 360)) -> Image.Image:
    """A colourful, textured image with corners for ORB to lock on to."""
    rng = np.random.default_rng(seed)
    w, h = size
    base = rng.integers(0, 256, size=(h // 8, w // 8, 3), dtype=np.uint8)
    img = Image.fromarray(base).resize(size, Image.Resampling.BICUBIC)
    draw = ImageDraw.Draw(img)
    r = random.Random(seed)
    for _ in range(40):
        x0, y0 = r.randint(0, w - 40), r.randint(0, h - 40)
        x1, y1 = x0 + r.randint(10, 80), y0 + r.randint(10, 80)
        colour = tuple(r.randint(0, 255) for _ in range(3))
        if r.random() < 0.5:
            draw.rectangle((x0, y0, x1, y1), fill=colour, outline="black")
        else:
            draw.ellipse((x0, y0, x1, y1), fill=colour, outline="white")
    return img


def to_image_data(item_id: str, img: Image.Image) -> ImageData:
    rgb = np.asarray(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return ImageData(id=item_id, rgb=rgb, gray=gray, embedding=None, phash=phash(gray))


@pytest.fixture
def photo() -> Image.Image:
    return synthetic_photo(1)


@pytest.fixture
def other_photo() -> Image.Image:
    return synthetic_photo(2)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(0)
