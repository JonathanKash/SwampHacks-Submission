"""Media plug-in interface: everything media-specific the core needs, in one object.

The core (candidates -> costs -> arborescence -> evidence) is identical for every
media type. A media plug-in supplies the three functions from SPEC.md plus a
loader. `ImageMedia` wraps the existing image modules; `TextMedia` lives in
plugins/text_media.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from lineage.plugins import image_cost, image_explain, image_features, image_fingerprint
from lineage.types import CostResult, Fingerprint


class MediaPlugin(Protocol):
    name: str

    def load(self, item_id: str, source: Any) -> Any:
        """Decode one item (a file path for images, a string for text) into item data."""

    def fingerprint(self, data: Any) -> Fingerprint:
        """Compact codes for candidate search (64-bit `phash` int + optional packed `code`)."""

    def cost(self, a: Any, b: Any) -> CostResult:
        """Asymmetric cost: how cheaply can b be produced from a. Lower is cheaper."""

    def explain(self, result: CostResult) -> tuple[str, str]:
        """(short edge label <= 28 chars, full sentence) for a chosen edge."""


class ImageMedia:
    name = "image"

    def __init__(self, embedder: image_fingerprint.ClipEmbedder | None) -> None:
        self.embedder = embedder

    def load(self, item_id: str, source: Any) -> Any:
        return image_fingerprint.load_image_data(item_id, Path(source), self.embedder)

    def fingerprint(self, data: Any) -> Fingerprint:
        return image_fingerprint.fingerprint(data)

    def cost(self, a: Any, b: Any) -> CostResult:
        return image_cost.cost(a, b)

    def explain(self, result: CostResult) -> tuple[str, str]:
        return image_explain.short_label(result), image_explain.explain(result)

    @staticmethod
    def stats(data: Any) -> image_features.ImageStats:
        """Cheap information cues; used by the eval's cue table (images only)."""
        return image_features.image_stats(data.rgb, data.gray)
