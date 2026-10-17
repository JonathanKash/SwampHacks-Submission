"""Shared dataclasses used by the core and the plug-ins."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Item:
    """One member of the pool. The engine never sees the true parent."""

    id: str
    path: Path
    media: str = "image"


@dataclass
class Fingerprint:
    """Compact codes used only for candidate search.

    phash: 64-bit perceptual hash packed into a Python int.
    code:  512-bit sign-binarized CLIP embedding packed with np.packbits
           (uint8 array of 64 bytes), or None when CLIP is unavailable.
    embedding: the float CLIP embedding (unit norm), kept for the semantic cost.
    """

    phash: int
    code: np.ndarray | None
    embedding: np.ndarray | None


@dataclass
class ImageData:
    """Decoded pixels of one image, as handed to cost()/explain()."""

    id: str
    rgb: np.ndarray  # (H, W, 3) uint8, downscaled to config.MAX_SIDE
    gray: np.ndarray  # (H, W) uint8
    embedding: np.ndarray | None  # unit-norm CLIP embedding or None
    phash: int


@dataclass
class CostResult:
    """Output of cost(a -> b).

    total:    the scalar cost (lower = b is more cheaply produced from a).
    semantic: True when registration failed and the semantic fallback was used.
    terms:    weighted contribution of each cost term (keys match config.WEIGHTS).
    features: raw measurements explain() builds its sentence from, e.g.
              area_ratio, angle_deg, color_gain (3,), color_bias (3,),
              blob_fraction, blockiness_a, blockiness_b, resolution_ratio, clip_cos.
    """

    total: float
    semantic: bool = False
    terms: dict[str, float] = field(default_factory=dict)
    features: dict[str, float | list[float]] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    """A directed candidate edge src -> dst with its computed cost."""

    src: str
    dst: str
    cost: float
    semantic: bool = False


@dataclass
class TreeResult:
    """parent[id] is the predicted parent id, or None when id is a root."""

    parent: dict[str, str | None]
    edges: dict[str, Edge] = field(default_factory=dict)  # dst -> chosen edge
