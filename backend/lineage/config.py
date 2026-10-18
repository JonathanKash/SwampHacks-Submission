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


# Default data dir is relative to the repo root, not the shell's cwd, so the server finds the
# same pool no matter where it is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(_REPO_ROOT / "data"))).resolve()

# Low-memory mode: USE_CLIP=false skips the CLIP model (~1.5 GB RAM). Candidate search then
# uses pHash only and "matched by meaning" edges use pHash distance. Fine for UI work and as a
# fallback on small machines; accuracy on restyles drops.
USE_CLIP: bool = _env_bool("USE_CLIP", True)

# Candidate search: how many likely relatives to keep per item.
CANDIDATE_K: int = 8
CANDIDATE_K_NO_CLIP: int = 16  # pHash-only mode (USE_CLIP=false) needs a wider net

# Images are downscaled to this max side before any analysis (speed + consistency).
MAX_SIDE: int = 768

# Cost of declaring an item a root (= attaching it to the virtual root in the
# arborescence). Must sit above any plausible "registered" edit cost and above a
# semantic edge between *related* images, but below a semantic edge between
# *unrelated* images, so unrelated families become separate trees (a forest).
ROOT_COST: float = 3.5

# Weights for plugins/image_cost.py. One dict, tune here.
# 2026-10-18 sweep (benchmark/weight_sweep.py, pHash-only): edit_op 0.05->0.1 and specificity 0.01->0.03
# raised held-out (run2+run3) tree accuracy 69.2% -> 70.9% with run1 unchanged; resolution/blockiness had no effect.
WEIGHTS: dict[str, float] = {
    # step 2: fraction of b not covered by warped a. Main direction signal.
    "coverage": 3.0,
    # step 3: MSE after per-channel affine color fit (pixels scaled to [0,1]).
    "color_residual": 1.0,
    # step 4: information-loss cues (only penalize the direction where b GAINS information).
    "blockiness": 1.0,  # JPEG 8x8 grid energy lost (only when geometry is unchanged)
    "resolution": 0.5,  # log pixel-count gain
    "chroma": 2.0,  # colorfulness gained from a grayscale source
    "entropy": 0.5,  # histogram entropy gained, bits (only when a color change was detected)
    # step 5: compact residual blobs where a has detail that b lacks (content removed).
    "blobs": 20.0,
    # step 6: a carries caption-like content (text/outline) in the changed region and b does not:
    # the a -> b direction removes a caption, which is rare (benchmark: caption side = copy 30/30).
    "caption_removed": 1.0,
    # step 7: description length, charged once per detected edit primitive.
    "edit_op": 0.1,
    # step 8: tie-breaker toward the most specific ancestor. Keep far below edit_op.
    "specificity": 0.03,
    # step 6: semantic fallback = semantic_offset + semantic_scale * (1 - cos).
    # The offset guarantees a semantic edge always costs more than a good registration.
    "semantic_offset": 2.0,
    "semantic_scale": 5.0,
}

# Registration is considered failed below this many RANSAC inliers, or when fewer
# than this fraction of ratio-test matches are inliers (guards spurious homographies).
# identify: a placement counts as a match only when the best parent explains the query at well
# under the root cost (a weak, barely-under-root match is reported as "no family").
IDENTIFY_MAX_COST_FRACTION: float = 0.8
# compare: colour-fit residual (MSE, 0-1 scale) above which an aligned pair is treated as re-rendered
# (restyle, background swap, generative re-draw): every pixel differs, so geometric cues like
# resolution and coverage no longer carry direction. Genuine edits on the synthetic runs stay below
# 0.022 (captions max 0.022, JPEG q8 max 0.013); Gemini restyles/background swaps measure 0.03-0.09.
RERENDER_RESIDUAL: float = 0.025
ORB_FEATURES: int = 4000  # keypoints per image for ORB (and the SIFT fallback)
MIN_INLIERS: int = 12
MIN_INLIER_RATIO: float = 0.25

# Blob detection: residual (0..1 scale) above which a pixel is "unexplained", and
# the minimum blob size as a fraction of the overlap area.
BLOB_RESIDUAL_THRESHOLD: float = 0.22
BLOB_MIN_AREA_FRACTION: float = 0.0005

# Below this mean colorfulness an image counts as grayscale (chroma cue applies).
GRAYSCALE_CHROMA: float = 0.05
# Color-fit MSE above which chroma in b is "unexplained" by a tint of gray a.
TINT_RESIDUAL_TOL: float = 0.005

# Edit-op detection thresholds (also used by explain()).
ROTATE_MIN_DEG: float = 0.5  # |homography angle| above this = a rotation happened
CROP_MAX_AREA_RATIO: float = 0.95  # pixels_b / pixels_a below this = a crop happened
COLOR_GAIN_TOL: float = 0.08  # |gain - 1| above this = brightness/contrast/tint changed
COLOR_BIAS_TOL: float = 0.03  # |bias| above this (0..1 scale) = tint/brightness changed
JPEG_MIN_BLOCKINESS_JUMP: float = 0.3  # blockiness(b) - blockiness(a) above this = re-saved as JPEG
BLOCKINESS_DEAD_ZONE: float = 0.15  # blockiness lost below this is noise, not an "un-JPEG"
