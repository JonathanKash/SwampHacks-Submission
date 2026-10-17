"""The shared core: pool -> fingerprints -> candidates -> cached costs -> arborescence.

Identical for every media type; media-specific behaviour comes from the plug-ins.
The engine never sees true parents.
"""

from __future__ import annotations

from pathlib import Path

from lineage import config
from lineage.core import arborescence, candidates
from lineage.plugins import image_cost, image_features, image_fingerprint
from lineage.types import CostResult, Edge, Fingerprint, ImageData, Item, TreeResult


class Engine:
    def __init__(
        self,
        k: int = config.CANDIDATE_K,
        root_cost: float = config.ROOT_COST,
        use_clip: bool = True,
    ) -> None:
        self.k = k
        self.root_cost = root_cost
        self.embedder = image_fingerprint.ClipEmbedder() if use_clip else None
        self.items: dict[str, Item] = {}
        self.data: dict[str, ImageData] = {}
        self.fingerprints: dict[str, Fingerprint] = {}
        self.stats: dict[str, image_features.ImageStats] = {}
        # Costs are cached per directed pair, which is what makes recomputation
        # after an upload incremental: only the new item's pairs are computed.
        self.results: dict[tuple[str, str], CostResult] = {}

    # ---- pool -------------------------------------------------------------
    def add_item(self, item_id: str, path: Path | str) -> None:
        """Decode, fingerprint and cache one new item. Costs are computed lazily."""
        item = Item(id=item_id, path=Path(path))
        data = image_fingerprint.load_image_data(item_id, item.path, self.embedder)
        self.items[item_id] = item
        self.data[item_id] = data
        self.fingerprints[item_id] = image_fingerprint.fingerprint(data)
        self.stats[item_id] = image_features.image_stats(data.rgb, data.gray)

    # ---- plug-ins ----------------------------------------------------------
    def cost(self, src: str, dst: str) -> CostResult:
        key = (src, dst)
        if key not in self.results:
            self.results[key] = image_cost.cost(self.data[src], self.data[dst])
        return self.results[key]

    # ---- tree -------------------------------------------------------------
    def build_tree(self) -> TreeResult:
        nodes = sorted(self.items)
        if not nodes:
            return TreeResult(parent={})
        neighbours = candidates.top_k_candidates(self.fingerprints, self.k)
        pairs: set[tuple[str, str]] = set()
        for i, near in neighbours.items():
            for j in near:
                pairs.add((i, j))
                pairs.add((j, i))  # both directions: cost decides which way
        edges = []
        for src, dst in sorted(pairs):
            result = self.cost(src, dst)
            edges.append(Edge(src=src, dst=dst, cost=float(result.total), semantic=result.semantic))
        parent = arborescence.minimum_arborescence(nodes, edges, self.root_cost)
        chosen = {e.dst: e for e in edges if parent.get(e.dst) == e.src}
        return TreeResult(parent=parent, edges=chosen)
