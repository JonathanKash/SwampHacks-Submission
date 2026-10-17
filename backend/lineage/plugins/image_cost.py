"""Image plug-in 2/3: cost(a -> b), asymmetric.

HAND-WRITTEN BY THE TEAM. Claude wrote only this interface, the docstrings and
backend/tests/test_image_cost.py. Do not let an AI fill in the bodies.

Spec (SPEC.md, "Image cost spec"):
1. ORB keypoints on a and b, BFMatcher(Hamming) + ratio test, cv2.findHomography
   with RANSAC mapping a -> b. Registration fails when there are fewer than
   config.MIN_INLIERS inliers (or no homography). On failure: return the semantic
   fallback (step 6) with semantic=True.
2. Warp a into b's frame (cv2.warpPerspective, size of b). Also warp an all-ones
   mask to find which pixels of b are covered. coverage_penalty = fraction of b's
   pixels NOT covered. (If b is a crop of a, warped a covers all of b: ~0. In the
   reverse direction most of the big image is uncovered: large.) Weight: "coverage".
3. On the covered overlap, fit per channel b_c ~= gain_c * a_c + bias_c by least
   squares. color_residual = MSE after the fit, with pixels scaled to [0, 1].
   Weight: "color_residual".
4. Information-loss cues (penalize only the direction where b has MORE information
   than a): blockiness: max(0, blockiness(a) - blockiness(b)); resolution:
   max(0, log(pixels_b / pixels_a)). plugins/image_features.py has helpers you may
   reuse or rewrite. Weights: "blockiness", "resolution".
5. Blobs: threshold the absolute residual (after the color fit) on the overlap, open/
   close it morphologically, and measure the fraction of overlap area inside
   connected components that are compact and above a minimum size (a caption).
   Present in b but not explained by a => penalty. Weight: "blobs".
6. Semantic fallback: semantic_offset + semantic_scale * (1 - cos(emb_a, emb_b)).
   When either embedding is None (CLIP unavailable, e.g. in unit tests), use the
   normalized pHash Hamming distance (bits differing / 64) instead of (1 - cos).

total = sum(weight * term). Also fill CostResult.features so explain() can say
what happened: area_ratio (area of b / area of a's warped footprint... or simply
pixels_b / pixels_a when registered), angle_deg (rotation extracted from the
homography), color_gain [3], color_bias [3], blob_fraction, blockiness_a,
blockiness_b, resolution_ratio, clip_cos.

Keep it readable: the judges will ask about every line.
"""

from __future__ import annotations

import numpy as np

from lineage import config
from lineage.types import CostResult, ImageData


def register(a: ImageData, b: ImageData) -> tuple[np.ndarray | None, int]:
    """Estimate the homography H (3x3) that maps a's pixel coordinates onto b's.

    Returns (H, inlier_count). H is None when registration fails.
    """
    raise NotImplementedError


def cost(a: ImageData, b: ImageData, weights: dict[str, float] = config.WEIGHTS) -> CostResult:
    """How cheaply can b be produced from a? Lower is cheaper. Must be asymmetric:
    for a real parent p and its edited child c, cost(p, c) < cost(c, p).

    Must never raise on valid images; must return a finite, non-negative total.
    """
    raise NotImplementedError
