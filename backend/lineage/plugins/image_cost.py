"""Image plug-in 2/3: cost(a -> b), asymmetric.

The question every term answers: "could b have been produced from a by a cheap,
lossy edit?" Terms only ever penalize the direction in which b would have had to
GAIN information that a does not have, because gaining information is what an
edit cannot do.

Steps (SPEC.md "Image cost spec"):
1. register: ORB keypoints, ratio-test matches, RANSAC homography a -> b.
   Fails -> semantic fallback (step 6), edge marked semantic.
2. coverage: warp a into b's frame; penalty = fraction of b NOT covered by a.
   A crop/rotate child is fully covered by its parent; the parent is not
   covered by the child. This is the main direction signal.
3. color: per-channel affine fit b ~ gain*a + bias on the overlap; residual MSE.
   Explains brightness/contrast/warm/cool cheaply in either direction, so it
   mostly measures "are these really the same picture".
4. information-loss cues, each max(0, information_b - information_a):
   - blockiness (JPEG 8x8 grid energy), only when the geometry is unchanged:
     rotating or rescaling destroys the grid legitimately.
   - resolution (pixel count).
   - chroma, only when a is grayscale: color cannot be recreated from gray.
   - histogram entropy, only when a brightness/contrast change was detected:
     scaling with rounding and clipping can only lose entropy.
5. blobs: compact regions of large residual where a has MORE edge energy than b.
   Content that exists in a but not in b must have been removed (expensive),
   whereas a caption that exists only in b was simply added (cheap).
6. semantic: semantic_offset + semantic_scale * (1 - cos(CLIP_a, CLIP_b)).
   Without embeddings (unit tests) the normalized pHash distance is used.
7. edit ops (minimum description length): a small constant per detected edit
   primitive (crop, rotate, color, jpeg, caption, grayscale). A child is one
   edit from its parent but two from its grandparent, so when residuals tie
   (which they do, edits are nearly lossless to the eye) the shorter
   explanation wins. This is what keeps chains in order.
8. specificity (tiny): among equally good explanations prefer the most specific
   ancestor, the candidate with the least surplus pixels/compression headroom.

Weights live in config.WEIGHTS. `features` in the result feeds explain().
"""

from __future__ import annotations

import hashlib
import math

import cv2
import numpy as np

from lineage import config
from lineage.plugins import image_features
from lineage.types import CostResult, ImageData

_orb = cv2.ORB_create(nfeatures=1500)
_matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

_feature_cache: dict[str, tuple[np.ndarray | None, np.ndarray | None]] = {}
_stats_cache: dict[str, image_features.ImageStats] = {}


def _key(img: ImageData) -> str:
    # Keyed by pixel content, not id: tests reuse ids, and pHash ignores brightness.
    if not img.content_key:
        img.content_key = hashlib.blake2b(img.rgb.tobytes(), digest_size=12).hexdigest()
    return img.content_key


def _orb_features(img: ImageData) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Keypoint coordinates (N, 2) and descriptors (N, 32), cached per image."""
    key = _key(img)
    if key not in _feature_cache:
        if len(_feature_cache) > 4000:
            _feature_cache.clear()
        keypoints, descriptors = _orb.detectAndCompute(img.gray, None)
        points = np.float32([kp.pt for kp in keypoints]) if keypoints else None
        _feature_cache[key] = (points, descriptors)
    return _feature_cache[key]


def _stats(img: ImageData) -> image_features.ImageStats:
    key = _key(img)
    if key not in _stats_cache:
        if len(_stats_cache) > 4000:
            _stats_cache.clear()
        _stats_cache[key] = image_features.image_stats(img.rgb, img.gray)
    return _stats_cache[key]


def register(a: ImageData, b: ImageData) -> tuple[np.ndarray | None, int]:
    """Estimate the homography H (3x3) mapping a's pixel coordinates onto b's.

    Returns (H, inlier_count); H is None when registration fails. A homography
    is rejected when it is not a plausible photo edit (flip, extreme scale,
    strong perspective), which also guards against spurious matches between
    unrelated images.
    """
    pts_a, des_a = _orb_features(a)
    pts_b, des_b = _orb_features(b)
    if des_a is None or des_b is None or len(des_a) < 2 or len(des_b) < 2:
        return None, 0
    good: list[cv2.DMatch] = []
    for pair in _matcher.knnMatch(des_a, des_b, k=2):
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:  # Lowe ratio test
            good.append(pair[0])
    if len(good) < config.MIN_INLIERS:
        return None, len(good)
    src = pts_a[[m.queryIdx for m in good]]
    dst = pts_b[[m.trainIdx for m in good]]
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if H is None or inliers < config.MIN_INLIERS or inliers < config.MIN_INLIER_RATIO * len(good):
        return None, inliers
    H = H / H[2, 2]
    det = float(np.linalg.det(H[:2, :2]))
    scale = math.sqrt(abs(det))
    if det <= 0 or not (0.25 <= scale <= 4.0) or abs(H[2, 0]) > 1e-3 or abs(H[2, 1]) > 1e-3:
        return None, inliers
    return H, inliers


def _semantic_cost(a: ImageData, b: ImageData, weights: dict[str, float], features: dict) -> CostResult:
    if a.embedding is not None and b.embedding is not None:
        cos = float(np.dot(a.embedding, b.embedding) / (np.linalg.norm(a.embedding) * np.linalg.norm(b.embedding)))
        distance = 1.0 - cos
        features["clip_cos"] = cos
    else:
        distance = (a.phash ^ b.phash).bit_count() / 64.0
    total = weights["semantic_offset"] + weights["semantic_scale"] * distance
    features["ops"] = ["restyle"]
    return CostResult(total=total, semantic=True, terms={"semantic": total}, features=features)


def cost(a: ImageData, b: ImageData, weights: dict[str, float] = config.WEIGHTS) -> CostResult:
    """How cheaply can b be produced from a? Lower is cheaper. For a real parent p
    and its edited child c, cost(p, c) < cost(c, p). Always finite and >= 0."""
    stats_a, stats_b = _stats(a), _stats(b)
    features: dict = {
        "blockiness_a": stats_a.blockiness,
        "blockiness_b": stats_b.blockiness,
        "resolution_ratio": stats_b.pixels / max(1, stats_a.pixels),
        "chroma_a": stats_a.chroma,
        "chroma_b": stats_b.chroma,
    }

    # --- 1. registration -----------------------------------------------------
    H, inliers = register(a, b)
    features["inliers"] = inliers
    if H is None:
        return _semantic_cost(a, b, weights, features)
    angle = math.degrees(math.atan2(H[1, 0], H[0, 0]))
    scale = math.sqrt(abs(float(np.linalg.det(H[:2, :2]))))
    geometry_unchanged = abs(angle) < config.ROTATE_MIN_DEG and abs(scale - 1.0) < 0.02
    features["angle_deg"] = angle
    features["scale"] = scale
    features["area_ratio"] = stats_b.pixels / max(1, stats_a.pixels)

    # --- 2. coverage ---------------------------------------------------------
    hb, wb = b.gray.shape
    warped = cv2.warpPerspective(a.rgb, H, (wb, hb), flags=cv2.INTER_LINEAR)
    ones = np.full(a.gray.shape, 255, dtype=np.uint8)
    covered = cv2.warpPerspective(ones, H, (wb, hb), flags=cv2.INTER_NEAREST) > 127
    overlap_px = int(covered.sum())
    if overlap_px < 0.02 * hb * wb or overlap_px < 256:
        return _semantic_cost(a, b, weights, features)  # a touches almost none of b
    coverage_penalty = 1.0 - overlap_px / (hb * wb)

    # --- 3. per-channel affine color fit on the overlap -------------------------
    # Moment matching (gain = std ratio, bias from the means) instead of least
    # squares: a few pixels of misregistration would shrink a least-squares slope
    # toward 0 ("regression dilution") and look like a fake brightness edit.
    src = warped[covered].astype(np.float32) / 255.0  # (N, 3)
    dst = b.rgb[covered].astype(np.float32) / 255.0
    src_std = src.std(axis=0)
    gains = np.where(src_std > 1e-3, dst.std(axis=0) / np.maximum(src_std, 1e-6), 1.0).astype(np.float32)
    biases = (dst.mean(axis=0) - gains * src.mean(axis=0)).astype(np.float32)
    fitted = np.clip(src * gains + biases, 0.0, 1.0)
    residual = fitted - dst  # (N, 3)
    color_residual = float((residual**2).mean())
    color_changed = bool(np.abs(gains - 1.0).max() > config.COLOR_GAIN_TOL or np.abs(biases).max() > config.COLOR_BIAS_TOL)
    features["color_gain"] = [float(g) for g in gains]
    features["color_bias"] = [float(v) for v in biases]

    # --- 4. information-loss cues (penalize b having MORE information) ----------
    # Dead zone: small blockiness differences are measurement noise.
    blockiness_drop = stats_a.blockiness - stats_b.blockiness - config.BLOCKINESS_DEAD_ZONE
    blockiness_term = min(1.0, max(0.0, blockiness_drop)) if geometry_unchanged else 0.0
    resolution_term = max(0.0, math.log(stats_b.pixels / max(1, stats_a.pixels)))
    a_is_gray = stats_a.chroma < config.GRAYSCALE_CHROMA
    chroma_term = max(0.0, stats_b.chroma - stats_a.chroma) if a_is_gray else 0.0
    jpeg_detected = stats_b.blockiness - stats_a.blockiness > config.JPEG_MIN_BLOCKINESS_JUMP
    # Histogram entropy only means something for a pure color edit: a
    # brightness/contrast change with rounding and clipping can only lose it,
    # whereas JPEG ringing and interpolation legitimately add some.
    pure_color_edit = color_changed and geometry_unchanged and not jpeg_detected
    entropy_term = max(0.0, stats_b.entropy - stats_a.entropy) if pure_color_edit else 0.0

    # Specificity tie-breaker (tiny weight): among candidates that explain b
    # equally well, prefer the one with the least surplus information, i.e. the
    # most specific ancestor (a crop of a crop is also one crop from the root).
    specificity = max(0.0, math.log(stats_a.pixels / max(1, stats_b.pixels))) + max(
        0.0, stats_b.blockiness - stats_a.blockiness
    )

    # --- 5. blobs: content present in a but missing from b ----------------------
    removed_fraction, added_fraction = _blob_fractions(warped, b.rgb, covered, residual)
    features["blob_fraction"] = removed_fraction
    features["added_blob_fraction"] = added_fraction

    # --- 7. edit ops detected in the a -> b direction (description length) ------
    ops: list[str] = []
    if abs(angle) >= config.ROTATE_MIN_DEG:
        ops.append("rotate")  # a rotation implies trimming the corners, so no extra crop op
    elif features["area_ratio"] < config.CROP_MAX_AREA_RATIO and coverage_penalty < 0.1:
        ops.append("crop")
    b_went_gray = stats_b.chroma < config.GRAYSCALE_CHROMA and stats_b.chroma < 0.25 * stats_a.chroma
    if not a_is_gray and b_went_gray:
        ops.append("grayscale")
    elif color_changed:
        ops.append("color")
    if jpeg_detected:
        ops.append("jpeg")
    if added_fraction > config.BLOB_MIN_AREA_FRACTION:
        ops.append("caption")
    features["ops"] = ops

    terms = {
        "coverage": weights["coverage"] * coverage_penalty,
        "color_residual": weights["color_residual"] * color_residual,
        "blockiness": weights["blockiness"] * blockiness_term,
        "resolution": weights["resolution"] * resolution_term,
        "chroma": weights["chroma"] * chroma_term,
        "entropy": weights["entropy"] * entropy_term,
        "blobs": weights["blobs"] * removed_fraction,
        "edit_ops": weights["edit_op"] * len(ops),
        "specificity": weights["specificity"] * specificity,
    }
    return CostResult(total=float(sum(terms.values())), semantic=False, terms=terms, features=features)


def _blob_fractions(
    warped: np.ndarray, target: np.ndarray, covered: np.ndarray, residual: np.ndarray
) -> tuple[float, float]:
    """(removed, added): fractions of the overlap inside compact high-residual blobs
    where the warped source has more edge energy than the target (detail that b
    lacks: removed) or less (detail only b has, e.g. a caption: added).

    JPEG noise is spread out and small, so the threshold and the morphological
    opening ignore it."""
    h, w = covered.shape
    magnitude = np.zeros((h, w), dtype=np.float32)
    magnitude[covered] = np.abs(residual).mean(axis=1)
    blob_mask = (magnitude > config.BLOB_RESIDUAL_THRESHOLD).astype(np.uint8)
    blob_mask = cv2.morphologyEx(blob_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    # Closing with a kernel ~2% of the image merges the letters of a caption into one blob.
    close = max(7, int(0.02 * max(h, w)) | 1)
    blob_mask = cv2.morphologyEx(blob_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (close, close)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(blob_mask, connectivity=8)
    if count <= 1:
        return 0.0, 0.0
    edges_src = np.abs(cv2.Laplacian(cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY), cv2.CV_32F))
    edges_dst = np.abs(cv2.Laplacian(cv2.cvtColor(target, cv2.COLOR_RGB2GRAY), cv2.CV_32F))
    overlap_px = int(covered.sum())
    min_area = max(30, int(config.BLOB_MIN_AREA_FRACTION * overlap_px))
    removed_area = added_area = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        bw, bh = int(stats[label, cv2.CC_STAT_WIDTH]), int(stats[label, cv2.CC_STAT_HEIGHT])
        # Compact blobs only: thin slivers along misregistered edges are not content.
        if area < min_area or min(bw, bh) < 6 or area < 0.25 * bw * bh:
            continue
        region = labels == label
        e_src, e_dst = float(edges_src[region].mean()), float(edges_dst[region].mean())
        if e_src > 1.5 * e_dst:
            removed_area += area
        elif e_dst > 1.5 * e_src:
            added_area += area
    return removed_area / overlap_px, added_area / overlap_px
