"""Noise-consistency indicator on synthetic composites."""

from __future__ import annotations

import numpy as np
from lineage.edits import image_edits
from lineage.plugins.noise import noise_consistency
from PIL import Image
from tests.conftest import synthetic_photo, to_image_data


def noisy(img: Image.Image, sigma: float, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    arr += rng.normal(0, sigma, arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def test_smooth_insert_breaks_noise_consistency():
    base = noisy(synthetic_photo(21), sigma=6.0, seed=1)
    composite = np.asarray(base).copy()
    h, w = composite.shape[:2]
    # a generated-looking patch: smooth gradient, no sensor noise
    y0, y1, x0, x1 = h // 3, h // 3 + h // 5, w // 3, w // 3 + w // 4
    grad = np.linspace(60, 200, x1 - x0, dtype=np.float32)
    composite[y0:y1, x0:x1] = np.stack([grad, grad * 0.8, grad * 0.6], axis=-1)[None].astype(np.uint8)
    rep = noise_consistency(to_image_data("A", base), to_image_data("B", Image.fromarray(composite)))
    assert rep and rep["measurable"] and rep["break"] and rep["ratio"] < 0.5


def test_plain_crop_keeps_noise_consistent():
    base = noisy(synthetic_photo(22), sigma=6.0, seed=2)
    import random

    crop = image_edits.crop(base, random.Random(3), fraction=0.7)[0]
    rep = noise_consistency(to_image_data("A", base), to_image_data("B", crop))
    # a crop changes nothing locally: either no region to measure, or a consistent one
    assert rep is None or not rep["measurable"] or not rep["break"]
