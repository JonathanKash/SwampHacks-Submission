"""Central configuration: environment flags and the tunable cost weights.

Everything tunable lives here so the team can adjust the cost in one place.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env if present (does nothing when the file is missing).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# TEMPORARY: when true, the engine uses core/fallback.py (networkx arborescence,
# brute-force candidates, crude cost) instead of the hand-written core files.
USE_FALLBACK: bool = _env_bool("USE_FALLBACK", True)

DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()

# Candidate search: how many likely relatives to keep per item.
CANDIDATE_K: int = 8

# Images are downscaled to this max side before any analysis (speed + consistency).
MAX_SIDE: int = 768

# Cost of declaring an item a root (= attaching it to the virtual root in the
# arborescence). Must sit above any plausible "registered" edit cost and above a
# semantic edge between *related* images, but below a semantic edge between
# *unrelated* images, so unrelated families become separate trees (a forest).
ROOT_COST: float = 3.5

# Weights for plugins/image_cost.py (hand-written). One dict, tune here.
WEIGHTS: dict[str, float] = {
    # step 2: fraction of b not covered by warped a. Main direction signal.
    "coverage": 3.0,
    # step 3: MSE after per-channel affine color fit (normalized to [0,1] pixel range).
    "color_residual": 1.0,
    # step 4: information-loss cues (only penalize the "gained information" direction).
    "blockiness": 0.5,
    "resolution": 0.5,
    # step 5: localized residual blobs present in b but not in a.
    "blobs": 0.5,
    # step 6: semantic fallback = semantic_offset + semantic_scale * (1 - cos).
    # The offset guarantees a semantic edge always costs more than a good registration.
    "semantic_offset": 2.0,
    "semantic_scale": 5.0,
}

# Registration is considered failed below this many RANSAC inliers.
MIN_INLIERS: int = 12
