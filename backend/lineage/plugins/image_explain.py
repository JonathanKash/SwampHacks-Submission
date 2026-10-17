"""Turn image cost features into concise, human-readable edit labels."""

from __future__ import annotations

from lineage.types import CostResult

_MAX_SHORT_LABEL = 28


def _ops(result: CostResult) -> set[str]:
    """Return the detected operations; image_cost stores them as a string list."""
    raw_ops = result.features.get("ops", [])
    if not isinstance(raw_ops, list):
        return set()
    return {op for op in raw_ops if isinstance(op, str)}


def _number(result: CostResult, name: str, default: float) -> float:
    value = result.features.get(name, default)
    return float(value) if isinstance(value, (int, float)) else default


def _channels(result: CostResult, name: str, default: float) -> tuple[float, float, float]:
    value = result.features.get(name)
    if not isinstance(value, list) or len(value) < 3:
        return (default, default, default)
    return float(value[0]), float(value[1]), float(value[2])


def _color_class(result: CostResult) -> tuple[str, str]:
    """Return the long and tree-label descriptions of an affine color edit."""
    gains = _channels(result, "color_gain", 1.0)
    biases = _channels(result, "color_bias", 0.0)
    effective = tuple(gain * 0.5 + bias for gain, bias in zip(gains, biases))
    mean_effective = sum(effective) / 3.0

    # Test tint before overall lightness: a warm filter may also lift the mean.
    if effective[0] - effective[2] > 0.06:
        return "warm filter", "warm"
    if effective[2] - effective[0] > 0.06:
        return "cool filter", "cool"
    if mean_effective > 0.54:
        return "brighter", "brighter"
    if mean_effective < 0.46:
        return "darker", "darker"
    if sum(gains) / 3.0 > 1.15:
        return "higher contrast", "contrast"
    return "color adjusted", "color"


def _rotation(result: CostResult, *, short: bool) -> str:
    angle = _number(result, "angle_deg", 0.0)
    if short:
        return f"rot {abs(angle):.1f}°"

    # Homographies use image coordinates, where +y points down. Therefore a
    # positive mathematical angle appears clockwise on the displayed image.
    direction = "clockwise" if angle >= 0.0 else "counter-clockwise"
    phrase = f"rotated {abs(angle):.1f}° {direction}"
    if _number(result, "area_ratio", 1.0) < 0.95:
        phrase += " (corners trimmed)"
    return phrase


def explain(result: CostResult) -> str:
    """Describe an edge using only measurements already stored in CostResult."""
    if result.semantic:
        return "AI restyle (matched by meaning)"

    ops = _ops(result)
    if not ops:
        return "near-identical copy"

    phrases: list[str] = []
    if "crop" in ops:
        phrases.append(f"cropped to {_number(result, 'area_ratio', 1.0) * 100:.0f}%")
    if "rotate" in ops:
        phrases.append(_rotation(result, short=False))
    if "color" in ops:
        phrases.append(_color_class(result)[0])
    if "grayscale" in ops:
        phrases.append("converted to grayscale")
    if "caption" in ops:
        phrases.append("caption added")
    if "jpeg" in ops:
        phrases.append("re-saved as low-quality JPEG")
    if "restyle" in ops:
        phrases.append("AI restyle")
    return ", ".join(phrases)


def short_label(result: CostResult) -> str:
    """Return a compact label suitable for a tree edge."""
    if result.semantic:
        return "restyle"

    ops = _ops(result)
    if not ops:
        return "copy"

    labels: list[str] = []
    if "crop" in ops:
        labels.append(f"crop {_number(result, 'area_ratio', 1.0) * 100:.0f}%")
    if "rotate" in ops:
        labels.append(_rotation(result, short=True))
    if "color" in ops:
        labels.append(_color_class(result)[1])
    if "grayscale" in ops:
        labels.append("gray")
    if "caption" in ops:
        labels.append("caption")
    if "jpeg" in ops:
        labels.append("jpeg")
    if "restyle" in ops:
        labels.append("restyle")

    label = " + ".join(labels)
    if len(label) > _MAX_SHORT_LABEL:
        return label[: _MAX_SHORT_LABEL - 1] + "…"
    return label
