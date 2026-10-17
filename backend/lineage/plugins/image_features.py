"""Cheap per-image "information content" statistics.

These are the raw information-loss cues from the cost spec (step 4) plus chroma
and distinct-levels cues. Used by plugins/image_cost.py and by the Phase 0
eval's per-cue direction table.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ImageStats:
    pixels: int  # effective resolution (H * W after the shared downscale)
    blockiness: float  # JPEG 8x8 grid energy (0 = none), max over grid offsets
    chroma: float  # mean colorfulness in [0, 1]; 0 for grayscale
    sharpness: float  # variance of the Laplacian
    levels: int  # distinct intensity values summed over R, G, B (max 768)
    entropy: float  # mean Shannon entropy (bits) of the per-channel histograms


def blockiness(gray: np.ndarray) -> float:
    """JPEG blockiness: how much stronger pixel differences are on an 8-pixel grid
    than elsewhere. Maximised over the 8 possible grid offsets per axis so that a
    cropped JPEG (misaligned grid) still scores high. 0.0 means no grid signal."""
    g = gray.astype(np.float32)
    col_diff = np.abs(g[:, 1:] - g[:, :-1]).mean(axis=0)  # per column boundary
    row_diff = np.abs(g[1:, :] - g[:-1, :]).mean(axis=1)  # per row boundary

    def grid_ratio(diffs: np.ndarray) -> float:
        base = diffs.mean() + 1e-6
        return max(diffs[o::8].mean() / base for o in range(8)) - 1.0

    return max(0.0, grid_ratio(col_diff)) + max(0.0, grid_ratio(row_diff))


def chroma(rgb: np.ndarray) -> float:
    spread = rgb.max(axis=2).astype(np.float32) - rgb.min(axis=2).astype(np.float32)
    return float(spread.mean() / 255.0)


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_32F).var())


def levels(rgb: np.ndarray) -> int:
    """Distinct values per channel, summed. Brightness/contrast changes with
    rounding and clipping can only reduce this; it is a cheap entropy proxy."""
    return int(sum(len(np.unique(rgb[:, :, c])) for c in range(3)))


def entropy(rgb: np.ndarray) -> float:
    """Mean per-channel histogram entropy in bits. Darkening merges values and
    clipping piles them up, both lower entropy; a caption or JPEG ringing adds a
    few new values but almost no entropy, so this is more robust than levels()."""
    total = 0.0
    for c in range(3):
        hist = np.bincount(rgb[:, :, c].ravel(), minlength=256).astype(np.float64)
        prob = hist[hist > 0] / hist.sum()
        total += float(-(prob * np.log2(prob)).sum())
    return total / 3.0


def image_stats(rgb: np.ndarray, gray: np.ndarray) -> ImageStats:
    return ImageStats(
        pixels=int(gray.shape[0] * gray.shape[1]),
        blockiness=float(blockiness(gray)),
        chroma=chroma(rgb),
        sharpness=sharpness(gray),
        levels=levels(rgb),
        entropy=entropy(rgb),
    )
