"""Caption-likeness of a changed region: is the content one image has and the other lacks
text-like (achromatic, both dark and bright, wide luminance spread) or natural?

Captions are added to images far more often than removed, so caption-like content present on
one side only is a directional cue. Thresholds come from measurements, see below.
"""

from __future__ import annotations

import numpy as np

# Thresholds set from measurements on synthetic captions (run1-3), a Gemini caption, Gemini object
# add/remove edits and the scene under a caption (see PLAN.md phase 8):
CAPTION_MIN_ACHROMATIC = 0.95  # share of changed pixels within 40 levels of gray; captions 0.95-1.0, scene under a caption 0.93
CAPTION_MIN_EXTREMES = 0.75  # share that is dark (<70) or bright (>185); captions 0.76-0.93, inpainted fill 0.34, scene 0.59
CAPTION_MIN_LUM_STD = 75  # luminance spread; captions 75-116, scene under a caption 69, fills/objects <= 59


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
    """Is the changed content in `rgb` caption-like? Measured on the region's pixels, robust to
    anti-aliasing (which turns two-tone text into grays): nearly all pixels achromatic, a real
    share both dark and bright, and a wide luminance spread. On our cases: real and synthetic
    captions measure achromatic >= 0.96, dark/bright >= 0.30, std >= 109; pasted objects,
    inpainted fills and the scene under a caption stay below std 72 or fail achromatic."""
    px = rgb[mask].astype(np.float32)
    if len(px) < 50:
        return {"two_tone": None, "caption_like": False}
    tt = _two_tone(rgb, mask)
    achromatic = float(((px.max(axis=1) - px.min(axis=1)) < 40).mean())
    lum = px.mean(axis=1)
    dark, bright, spread = float((lum < 70).mean()), float((lum > 185).mean()), float(lum.std())
    return {"two_tone": round(tt[0], 3) if tt else None, "achromatic": round(achromatic, 2), "dark": round(dark, 2),
            "bright": round(bright, 2), "lum_std": round(spread, 1),
            "caption_like": bool(achromatic >= CAPTION_MIN_ACHROMATIC and dark + bright >= CAPTION_MIN_EXTREMES
                                 and spread >= CAPTION_MIN_LUM_STD)}
