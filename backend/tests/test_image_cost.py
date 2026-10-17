"""Specification for the hand-written plugins/image_cost.py.

Images come from the fixtures (no CLIP; embedding is None, so the semantic
fallback uses the pHash distance). Each edit is produced by the same edit menu
the demo uses.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lineage import config
from lineage.edits import image_edits
from lineage.plugins.image_cost import cost, register
from tests.conftest import to_image_data

EDITS = ["crop", "rotate", "caption", "jpeg", "filter:grayscale", "filter:warm", "filter:darker", "filter:contrast"]


def make_child(photo, edit: str, rng):
    if edit.startswith("filter:"):
        return image_edits.color_filter(photo, rng, kind=edit.split(":")[1])[0]
    return image_edits.apply_edit(photo, edit, rng)[0]


# ---- register -----------------------------------------------------------------

def test_register_identical_images_gives_near_identity(photo):
    a = to_image_data("a", photo)
    H, inliers = register(a, a)
    assert H is not None and H.shape == (3, 3)
    assert inliers >= config.MIN_INLIERS
    assert np.allclose(H / H[2, 2], np.eye(3), atol=0.05)


def test_register_crop_recovers_translation(photo, rng):
    child_img, params = image_edits.crop(photo, rng, fraction=0.6)
    a, b = to_image_data("a", photo), to_image_data("b", child_img)
    H, inliers = register(a, b)
    assert H is not None and inliers >= config.MIN_INLIERS
    H = H / H[2, 2]
    x0, y0 = params["box"][0], params["box"][1]
    assert H[0, 2] == pytest.approx(-x0, abs=3)
    assert H[1, 2] == pytest.approx(-y0, abs=3)


def test_register_fails_on_unrelated_images(photo, other_photo):
    H, inliers = register(to_image_data("a", photo), to_image_data("b", other_photo))
    assert H is None or inliers < config.MIN_INLIERS


# ---- cost: shape of the result -------------------------------------------------

def test_cost_result_is_finite_nonnegative_with_terms(photo, rng):
    child = to_image_data("b", make_child(photo, "crop", rng))
    result = cost(to_image_data("a", photo), child)
    assert math.isfinite(result.total) and result.total >= 0
    assert result.semantic is False
    assert set(result.terms) >= {"coverage", "color_residual", "blockiness", "resolution", "chroma", "entropy", "blobs", "edit_ops", "specificity"}
    assert all(v >= 0 for v in result.terms.values())
    assert result.total == pytest.approx(sum(result.terms.values()))


def test_identical_images_cost_almost_nothing(photo):
    a = to_image_data("a", photo)
    assert cost(a, to_image_data("a2", photo)).total < 0.05


# ---- cost: the asymmetry that makes the whole project work ---------------------

@pytest.mark.parametrize("edit", EDITS)
def test_parent_to_child_is_cheaper_than_reverse(photo, rng, edit):
    parent = to_image_data("p", photo)
    child = to_image_data("c", make_child(photo, edit, rng))
    forward = cost(parent, child)
    backward = cost(child, parent)
    assert forward.semantic is False, f"{edit}: registration should succeed"
    assert forward.total < backward.total, f"{edit}: forward {forward.total:.3f} >= backward {backward.total:.3f}"


def test_crop_direction_is_driven_by_coverage(photo, rng):
    parent = to_image_data("p", photo)
    child = to_image_data("c", image_edits.crop(photo, rng, fraction=0.5)[0])
    forward, backward = cost(parent, child), cost(child, parent)
    assert forward.terms["coverage"] < 0.1 * config.WEIGHTS["coverage"]
    assert backward.terms["coverage"] > 0.3 * config.WEIGHTS["coverage"]


def test_jpeg_direction_is_driven_by_blockiness(photo, rng):
    parent = to_image_data("p", photo)
    child = to_image_data("c", image_edits.jpeg(photo, rng, quality=10)[0])
    assert cost(parent, child).terms["blockiness"] == pytest.approx(0.0, abs=1e-6)
    assert cost(child, parent).terms["blockiness"] > 0


def test_caption_direction_is_driven_by_blobs(photo, rng):
    # Removing the caption (child -> parent) is the expensive direction.
    parent = to_image_data("p", photo)
    child = to_image_data("c", image_edits.caption(photo, rng, text="SWAMPHACKS")[0])
    assert cost(parent, child).terms["blobs"] == pytest.approx(0.0, abs=1e-6)
    assert cost(child, parent).terms["blobs"] > 0


def test_two_step_child_still_closer_to_parent_than_to_stranger(photo, other_photo, rng):
    parent = to_image_data("p", photo)
    step1 = image_edits.crop(photo, rng, fraction=0.7)[0]
    child = to_image_data("c", image_edits.color_filter(step1, rng, kind="warm")[0])
    stranger = to_image_data("s", other_photo)
    assert cost(parent, child).total < cost(stranger, child).total


# ---- semantic fallback ----------------------------------------------------------

def test_unrelated_images_use_semantic_fallback_and_cost_more(photo, other_photo, rng):
    a, b = to_image_data("a", photo), to_image_data("b", other_photo)
    unrelated = cost(a, b)
    assert unrelated.semantic is True
    assert unrelated.total >= config.WEIGHTS["semantic_offset"]
    related = cost(a, to_image_data("c", make_child(photo, "crop", rng)))
    assert unrelated.total > related.total


def test_semantic_fallback_uses_embeddings_when_present(photo, other_photo):
    a, b = to_image_data("a", photo), to_image_data("b", other_photo)
    a.embedding = np.array([1.0, 0.0], dtype=np.float32)
    b.embedding = np.array([0.6, 0.8], dtype=np.float32)  # cos = 0.6
    result = cost(a, b)
    assert result.semantic is True
    expected = config.WEIGHTS["semantic_offset"] + config.WEIGHTS["semantic_scale"] * (1 - 0.6)
    assert result.total == pytest.approx(expected, rel=1e-3)
    assert result.features.get("clip_cos") == pytest.approx(0.6, abs=1e-3)


# ---- features for explain() --------------------------------------------------------

def test_features_describe_crop_and_rotation(photo, rng):
    parent = to_image_data("p", photo)
    crop_child = to_image_data("c", image_edits.crop(photo, rng, fraction=0.5)[0])
    feats = cost(parent, crop_child).features
    assert feats["area_ratio"] == pytest.approx(0.5, abs=0.08)
    assert abs(feats["angle_deg"]) < 1.0

    rot_child = to_image_data("r", image_edits.rotate(photo, rng, angle=8.0)[0])
    feats = cost(parent, rot_child).features
    assert abs(abs(feats["angle_deg"]) - 8.0) < 1.5


def test_features_describe_color_change(photo, rng):
    parent = to_image_data("p", photo)
    dark = to_image_data("d", image_edits.color_filter(photo, rng, kind="darker")[0])
    gain = cost(parent, dark).features["color_gain"]
    assert len(gain) == 3 and all(g < 0.9 for g in gain)


# ---- edit-op detection (description length prior) ----------------------------------

@pytest.mark.parametrize("edit,expected_op", [
    ("crop", "crop"), ("rotate", "rotate"), ("jpeg", "jpeg"), ("caption", "caption"),
    ("filter:grayscale", "grayscale"), ("filter:darker", "color"), ("filter:contrast", "color"),
])
def test_detects_the_edit_that_was_applied(photo, rng, edit, expected_op):
    parent = to_image_data("p", photo)
    child = to_image_data("c", make_child(photo, edit, rng))
    assert expected_op in cost(parent, child).features["ops"]


def test_identical_images_have_no_ops(photo):
    assert cost(to_image_data("a", photo), to_image_data("a2", photo)).features["ops"] == []


def test_direct_parent_beats_grandparent(photo, rng):
    # grandparent -> parent (crop) -> child (darker). The child must prefer its parent.
    grand = to_image_data("g", photo)
    parent_img = image_edits.crop(photo, rng, fraction=0.7)[0]
    parent = to_image_data("p", parent_img)
    child = to_image_data("c", image_edits.color_filter(parent_img, rng, kind="darker")[0])
    assert cost(parent, child).total < cost(grand, child).total
