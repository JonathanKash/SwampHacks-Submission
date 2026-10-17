"""Noise-consistency check for a registered pair: does the changed region of the copy carry
the same sensor/compression noise as the rest of it?

A camera photo has roughly uniform fine-grain noise. A region that was generated, filled
or pasted in usually does not: generative fills are smoother, pasted content brings the
noise of another file. We measure the high-pass residual (pixel minus a 3x3 median) inside
the region where the copy differs from the aligned source, and outside it. A large ratio
is a measured indicator of a composite, not proof of AI use.
"""

from __future__ import annotations

import cv2
import numpy as np

from lineage import config
from lineage.plugins import image_cost
from lineage.types import ImageData

CHANGE_THRESHOLD = 0.12  # residual after color fit that counts as "changed"
MIN_REGION = 0.002  # fraction of the frame; smaller regions give unstable statistics
MAX_REGION = 0.6  # above this it is a restyle, not a local edit
BREAK_RATIO = 1.6  # noise differs by this factor either way -> indicator
CAPTION_TWO_TONE = 0.7  # at least this fraction of the strongly-changed pixels in two colours
# (synthetic captions measure ~0.83 after anti-aliasing; pasted natural patches ~0.10)
CAPTION_MAX_SATURATION = 40  # both colour centres within 40 levels of gray (white/black text)
CAPTION_MIN_CONTRAST = 100  # luminance gap between the two centres; a flat inpainted patch has none


def _two_tone(rgb: np.ndarray, mask: np.ndarray) -> tuple[float, np.ndarray, np.ndarray] | None:
    """(fraction of the region's pixels within 40 levels of one of two colour centres, c1, c2)
    by 2-means. Text and outlines are two-tone; a natural object is not."""
    px = rgb[mask].astype(np.float32)
    if len(px) < 50:
        return None
    c1, c2 = px.min(axis=0), px.max(axis=0)
    d1 = d2 = None
    for _ in range(8):
        d1 = ((px - c1) ** 2).sum(axis=1)
        d2 = ((px - c2) ** 2).sum(axis=1)
        near1 = d1 < d2
        if near1.sum() == 0 or (~near1).sum() == 0:
            break
        c1, c2 = px[near1].mean(axis=0), px[~near1].mean(axis=0)
    dist = np.sqrt(np.minimum(d1, d2))
    return float((dist < 40).mean()), c1, c2


def caption_likeness(rgb: np.ndarray, mask: np.ndarray) -> dict:
    """Is the changed content in `rgb` caption-like? Three measured conditions, all required:
    two-tone (>= CAPTION_TWO_TONE of pixels near one of two colours), both colours nearly
    achromatic (text is typically white/black), and strong contrast between them (an
    inpainted flat patch is also two-tone, but its two centres are close together)."""
    tt = _two_tone(rgb, mask)
    if tt is None:
        return {"two_tone": None, "caption_like": False}
    frac, c1, c2 = tt
    sat = max(float(c1.max() - c1.min()), float(c2.max() - c2.min()))
    contrast = abs(float(c1.mean() - c2.mean()))
    return {"two_tone": round(frac, 3), "achromatic": sat < CAPTION_MAX_SATURATION, "contrast": round(contrast, 1),
            "caption_like": bool(frac >= CAPTION_TWO_TONE and sat < CAPTION_MAX_SATURATION and contrast >= CAPTION_MIN_CONTRAST)}


def _highpass_std(gray: np.ndarray, mask: np.ndarray) -> float | None:
    if mask.sum() < 200:
        return None
    med = cv2.medianBlur(gray, 3)
    resid = gray.astype(np.float32) - med.astype(np.float32)
    return float(resid[mask].std())


def noise_consistency(source: ImageData, copy: ImageData) -> dict | None:
    """Return measurements for the source->copy direction, or None when nothing can be measured
    (no alignment, or no local change region of usable size)."""
    H, inliers = image_cost.register(source, copy)
    if H is None:
        return None
    hb, wb = copy.gray.shape
    warped = cv2.warpPerspective(source.rgb, H, (wb, hb), flags=cv2.INTER_LINEAR)
    covered = cv2.warpPerspective(np.full(source.gray.shape, 255, np.uint8), H, (wb, hb), flags=cv2.INTER_NEAREST) > 127
    src = warped.astype(np.float32) / 255.0
    dst = copy.rgb.astype(np.float32) / 255.0
    if covered.sum() < 500:
        return None
    std = src[covered].std(axis=0)
    gains = np.where(std > 1e-3, dst[covered].std(axis=0) / np.maximum(std, 1e-6), 1.0)
    biases = dst[covered].mean(axis=0) - gains * src[covered].mean(axis=0)
    residual = np.abs(np.clip(src * gains + biases, 0, 1) - dst).mean(axis=2)
    changed = (residual > CHANGE_THRESHOLD) & covered
    # Colour structure is measured on the strongly-changed pixels only (the strokes of a
    # caption, the body of an object), before the mask is cleaned and grown.
    strong = (residual > config.BLOB_RESIDUAL_THRESHOLD) & covered
    # Clean the mask: drop speckle, then grow it slightly so edges of the insert are inside it.
    changed = cv2.morphologyEx(changed.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
    changed = cv2.dilate(changed.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    frac = float(changed.mean())
    if frac < MIN_REGION or frac > MAX_REGION:
        return {"region_fraction": round(frac, 4), "measurable": False}
    # Is the content the copy gained in that region caption-like (text/outline) or natural?
    cap = caption_likeness(copy.rgb, strong)
    two_tone = cap["two_tone"] if cap["two_tone"] is not None else 0.0
    unchanged = covered & ~changed
    # Erode the unchanged area away from the boundary so blur halos do not leak in.
    unchanged = cv2.erode(unchanged.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    inside = _highpass_std(copy.gray, changed)
    outside = _highpass_std(copy.gray, unchanged)
    if inside is None or outside is None or outside < 1e-3:
        return {"region_fraction": round(frac, 4), "measurable": False, **cap}
    ratio = inside / outside
    return {
        "measurable": True,
        "region_fraction": round(frac, 4),
        "noise_inside_changed": round(inside, 3),
        "noise_outside": round(outside, 3),
        "ratio": round(ratio, 3),
        "break": bool(ratio > BREAK_RATIO or ratio < 1 / BREAK_RATIO),
        **cap,
        "max_side": config.MAX_SIDE,
    }
