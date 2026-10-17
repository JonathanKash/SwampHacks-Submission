"""The shared core: pool -> fingerprints -> candidates -> cached costs -> arborescence.

Identical for every media type; media-specific behaviour comes from the plug-ins.
The engine never sees true parents.
"""

from __future__ import annotations

from pathlib import Path

from lineage import config
from lineage.core import fallback
from lineage.plugins import image_features, image_fingerprint
from lineage.types import Edge, Fingerprint, ImageData, Item, TreeResult


class Engine:
    def __init__(
        self,
        use_fallback: bool = config.USE_FALLBACK,
        k: int = config.CANDIDATE_K,
        root_cost: float = config.ROOT_COST,
        use_clip: bool = True,
    ) -> None:
        self.use_fallback = use_fallback
        self.k = k
        self.root_cost = root_cost
        self.embedder = image_fingerprint.ClipEmbedder() if use_clip else None
        self.items: dict[str, Item] = {}
        self.data: dict[str, ImageData] = {}
        self.fingerprints: dict[str, Fingerprint] = {}
        self.stats: dict[str, image_features.ImageStats] = {}
        self.cost_cache: dict[tuple[str, str], Edge] = {}

    # ---- pool -------------------------------------------------------------
    def add_item(self, item_id: str, path: Path | str) -> None:
        """Decode, fingerprint and cache one new item. Costs are computed lazily."""
        item = Item(id=item_id, path=Path(path))
        data = image_fingerprint.load_image_data(item_id, item.path, self.embedder)
        self.items[item_id] = item
        self.data[item_id] = data
        self.fingerprints[item_id] = image_fingerprint.fingerprint(data)
        self.stats[item_id] = image_features.image_stats(data.rgb, data.gray)

    # ---- plug-in selection ------------------------------------------------
    def _candidates(self) -> dict[str, list[str]]:
        if self.use_fallback:
            return fallback.all_pairs_candidates(self.fingerprints, self.k)
        from lineage.core import candidates  # hand-written

        return candidates.top_k_candidates(self.fingerprints, self.k)

    def _cost(self, src: str, dst: str) -> Edge:
        key = (src, dst)
        if key in self.cost_cache:
            return self.cost_cache[key]
        if self.use_fallback:
            result = fallback.crude_cost(self.data[src], self.data[dst], self.stats[src], self.stats[dst])
        else:
            from lineage.plugins import image_cost  # hand-written

            result = image_cost.cost(self.data[src], self.data[dst])
        edge = Edge(src=src, dst=dst, cost=float(result.total), semantic=result.semantic)
        self.cost_cache[key] = edge
        return edge

    def _arborescence(self, nodes: list[str], edges: list[Edge]) -> dict[str, str | None]:
        if self.use_fallback:
            return fallback.networkx_arborescence(nodes, edges, self.root_cost)
        from lineage.core import arborescence  # hand-written

        return arborescence.minimum_arborescence(nodes, edges, self.root_cost)

    # ---- tree -------------------------------------------------------------
    def build_tree(self) -> TreeResult:
        """Recompute the tree. Incremental in practice: costs are cached per pair,
        so adding one item only costs its new candidate pairs."""
        nodes = sorted(self.items)
        if not nodes:
            return TreeResult(parent={})
        candidates = self._candidates()
        pairs: set[tuple[str, str]] = set()
        for i, neighbours in candidates.items():
            for j in neighbours:
                pairs.add((i, j))
                pairs.add((j, i))
        edges = [self._cost(src, dst) for src, dst in sorted(pairs)]
        parent = self._arborescence(nodes, edges)
        chosen = {e.dst: e for e in edges if parent.get(e.dst) == e.src}
        return TreeResult(parent=parent, edges=chosen)
