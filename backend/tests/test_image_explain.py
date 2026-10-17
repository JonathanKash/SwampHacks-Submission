"""Unit tests for descriptions built directly from CostResult features."""

from __future__ import annotations

import pytest
from lineage.plugins.image_explain import explain, short_label
from lineage.types import CostResult


def result(*ops: str, semantic: bool = False, **features: object) -> CostResult:
    """Build a cost result without reading or constructing any images."""
    feature_values: dict = {"ops": list(ops), **features}
    return CostResult(total=0.0, semantic=semantic, terms={}, features=feature_values)


def test_semantic_edge_has_the_fixed_explanation() -> None:
    edge = result("restyle", semantic=True, area_ratio=0.1)
    assert explain(edge) == "AI restyle (matched by meaning)"
    assert short_label(edge) == "restyle"


def test_no_operations_is_a_copy() -> None:
    edge = result()
    assert explain(edge) == "near-identical copy"
    assert short_label(edge) == "copy"


def test_crop_uses_parent_area_percentage() -> None:
    edge = result("crop", area_ratio=0.624)
    assert explain(edge) == "cropped to 62%"
    assert short_label(edge) == "crop 62%"


def test_positive_rotation_is_clockwise_in_downward_y_coordinates() -> None:
    edge = result("rotate", angle_deg=7.44, area_ratio=0.95)
    assert explain(edge) == "rotated 7.4° clockwise"
    assert short_label(edge) == "rot 7.4°"


def test_negative_rotation_reports_trimmed_corners() -> None:
    edge = result("rotate", angle_deg=-8.26, area_ratio=0.94)
    assert explain(edge) == "rotated 8.3° counter-clockwise (corners trimmed)"


@pytest.mark.parametrize(
    ("gains", "biases", "description", "label"),
    [
        ([1.0, 1.0, 1.0], [0.08, 0.0, 0.0], "warm filter", "warm"),
        ([1.0, 1.0, 1.0], [0.0, 0.0, 0.08], "cool filter", "cool"),
        ([1.0, 1.0, 1.0], [0.05, 0.05, 0.05], "brighter", "brighter"),
        ([1.0, 1.0, 1.0], [-0.05, -0.05, -0.05], "darker", "darker"),
        ([1.2, 1.2, 1.2], [-0.1, -0.1, -0.1], "higher contrast", "contrast"),
        ([1.1, 1.1, 1.1], [-0.05, -0.05, -0.05], "color adjusted", "color"),
    ],
)
def test_color_classification(
    gains: list[float], biases: list[float], description: str, label: str
) -> None:
    edge = result("color", color_gain=gains, color_bias=biases)
    assert explain(edge) == description
    assert short_label(edge) == label


@pytest.mark.parametrize(
    ("op", "description", "label"),
    [
        ("grayscale", "converted to grayscale", "gray"),
        ("caption", "content added (caption or object)", "added"),
        ("jpeg", "re-saved as low-quality JPEG", "jpeg"),
        ("restyle", "AI restyle", "restyle"),
    ],
)
def test_single_operation_descriptions(op: str, description: str, label: str) -> None:
    edge = result(op)
    assert explain(edge) == description
    assert short_label(edge) == label


def test_multiple_operations_use_canonical_order() -> None:
    # Deliberately scramble input so display order cannot depend on list order.
    edge = result(
        "jpeg",
        "caption",
        "color",
        "rotate",
        "crop",
        area_ratio=0.62,
        angle_deg=-7.35,
        color_gain=[1.0, 1.0, 1.0],
        color_bias=[0.08, 0.0, 0.0],
    )
    assert explain(edge) == (
        "cropped to 62%, rotated 7.3° counter-clockwise (corners trimmed), "
        "warm filter, content added (caption or object), re-saved as low-quality JPEG"
    )


def test_short_label_is_truncated_to_28_characters() -> None:
    edge = result(
        "crop",
        "rotate",
        "color",
        "caption",
        "jpeg",
        area_ratio=0.62,
        angle_deg=12.34,
        color_gain=[1.0, 1.0, 1.0],
        color_bias=[0.08, 0.0, 0.0],
    )
    label = short_label(edge)
    assert label == "crop 62% + rot 12.3° + warm…"
    assert len(label) == 28
