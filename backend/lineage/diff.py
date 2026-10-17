"""Visual diff plate for a decision: source warped onto the derived copy, side by side
with a residual heatmap. This is the evidence an auditor can look at, not just read.

Layout (one PNG): [ source warped into the copy's frame | the copy | residual heatmap ]
Uncovered pixels (the copy has content the source cannot supply) are hatched dark in
the first panel; the heatmap is |color-fitted source - copy| per pixel.
"""

from __future__ import annotations

import cv2
import numpy as np

from lineage.plugins import image_cost
from lineage.types import ImageData

PANEL_MAX = 420


def _fit(img: np.ndarray, max_side: int = PANEL_MAX) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    return img


def _label(panel: np.ndarray, text: str) -> np.ndarray:
    out = panel.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 26), (12, 18, 17), -1)
    cv2.putText(out, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (98, 230, 166), 1, cv2.LINE_AA)
    return out


def diff_plate(source: ImageData, copy: ImageData) -> tuple[np.ndarray, dict]:
    """Return (RGB image, info). info: registered(bool), coverage, inliers."""
    H, inliers = image_cost.register(source, copy)
    hb, wb = copy.gray.shape
    info: dict = {"registered": H is not None, "inliers": int(inliers)}
    if H is None:
        # Nothing aligns: show both images and an empty heatmap note.
        left = _label(_fit(source.rgb), "source (no alignment)")
        right = _label(_fit(copy.rgb), "derived copy")
        heat = np.full_like(right, 20)
        cv2.putText(heat, "matched by meaning only", (10, heat.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        info["coverage"] = None
        return _hstack([left, right, _label(heat, "residual")]), info

    warped = cv2.warpPerspective(source.rgb, H, (wb, hb), flags=cv2.INTER_LINEAR)
    ones = np.full(source.gray.shape, 255, dtype=np.uint8)
    covered = cv2.warpPerspective(ones, H, (wb, hb), flags=cv2.INTER_NEAREST) > 127
    info["coverage"] = round(float(covered.mean()), 4)

    # Same moment-matched color fit as the cost, so the residual shows real differences,
    # not a global brightness shift.
    src = warped.astype(np.float32) / 255.0
    dst = copy.rgb.astype(np.float32) / 255.0
    cov_src, cov_dst = src[covered], dst[covered]
    if len(cov_src) > 16:
        std = cov_src.std(axis=0)
        gains = np.where(std > 1e-3, cov_dst.std(axis=0) / np.maximum(std, 1e-6), 1.0)
        biases = cov_dst.mean(axis=0) - gains * cov_src.mean(axis=0)
        fitted = np.clip(src * gains + biases, 0, 1)
    else:
        fitted = src
    residual = np.abs(fitted - dst).mean(axis=2)  # 0..1
    residual[~covered] = 0
    heat = cv2.applyColorMap(np.clip(residual * 255 * 3, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    heat[~covered] = (40, 40, 40)

    shown = warped.copy()
    # Hatch the uncovered area: content the source cannot supply.
    hatch = np.zeros_like(shown)
    hatch[::6, :] = (120, 40, 60)
    shown[~covered] = (shown[~covered] * 0.25 + hatch[~covered]).astype(np.uint8)

    left = _label(_fit(shown), f"source aligned onto copy  ({inliers} inliers)")
    middle = _label(_fit(copy.rgb), "derived copy")
    right = _label(_fit(heat), "residual after color fit")
    return _hstack([left, middle, right]), info


def _hstack(panels: list[np.ndarray]) -> np.ndarray:
    h = max(p.shape[0] for p in panels)
    padded = []
    for p in panels:
        pad = np.full((h, p.shape[1], 3), 12, dtype=np.uint8)
        pad[: p.shape[0], :] = p
        padded.append(pad)
    gap = np.full((h, 8, 3), 12, dtype=np.uint8)
    out = padded[0]
    for p in padded[1:]:
        out = np.hstack([out, gap, p])
    return out


def encode_png(rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("could not encode diff plate")
    return buf.tobytes()
