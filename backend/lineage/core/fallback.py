"""TEMPORARY stand-ins for the three hand-written files, so the app runs end to end
while the team writes the real ones. Selected by USE_FALLBACK=true.

Everything here is deliberately crude:
- candidates: brute force (every other item), ignores k.
- arborescence: networkx's Edmonds implementation with the virtual-root trick.
- cost: no registration at all. Semantic distance plus cheap one-directional
  information-loss cues (resolution, JPEG blockiness, chroma). It cannot tell the
  direction of a rotate, caption or non-grayscale filter; that is what the real
  cost's coverage / color-fit / blob terms are for.

Delete this file once USE_FALLBACK is retired.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import networkx as nx
import numpy as np

from lineage.plugins.image_features import ImageStats
from lineage.types import CostResult, Edge, Fingerprint, ImageData

VIRTUAL_ROOT = "__virtual_root__"


def all_pairs_candidates(fingerprints: dict[str, Fingerprint], k: int = 8) -> dict[str, list[str]]:
    """TEMPORARY: every other item is a candidate (O(n^2) costs)."""
    ids = sorted(fingerprints)
    return {i: [j for j in ids if j != i] for i in ids}


def networkx_arborescence(
    nodes: Sequence[str], edges: Sequence[Edge], root_cost: float
) -> dict[str, str | None]:
    """TEMPORARY: minimum spanning arborescence via networkx + virtual root."""
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    node_set = set(nodes)
    for node in nodes:
        graph.add_edge(VIRTUAL_ROOT, node, weight=root_cost)
    for edge in edges:
        if edge.src == edge.dst or edge.src not in node_set or edge.dst not in node_set:
            continue
        existing = graph.get_edge_data(edge.src, edge.dst)
        if existing is None or edge.cost < existing["weight"]:
            graph.add_edge(edge.src, edge.dst, weight=edge.cost)
    tree = nx.minimum_spanning_arborescence(graph, attr="weight")
    parent: dict[str, str | None] = {}
    for node in nodes:
        preds = list(tree.predecessors(node))
        parent[node] = None if not preds or preds[0] == VIRTUAL_ROOT else preds[0]
    return parent


def _semantic_distance(a: ImageData, b: ImageData) -> float:
    if a.embedding is not None and b.embedding is not None:
        return float(1.0 - np.dot(a.embedding, b.embedding))
    return bin(a.phash ^ b.phash).count("1") / 64.0


def crude_cost(a: ImageData, b: ImageData, stats_a: ImageStats, stats_b: ImageStats) -> CostResult:
    """TEMPORARY crude asymmetric cost. See module docstring for what it cannot do."""
    semantic = _semantic_distance(a, b)
    # Each cue only penalizes the direction in which b would have GAINED information.
    resolution_gain = max(0.0, math.log(stats_b.pixels / max(1, stats_a.pixels)))
    blockiness_loss = max(0.0, stats_a.blockiness - stats_b.blockiness)
    chroma_gain = max(0.0, stats_b.chroma - stats_a.chroma)
    terms = {
        "semantic": 1.0 * semantic,
        "resolution": 1.0 * resolution_gain,
        "blockiness": 1.0 * blockiness_loss,
        "chroma": 2.0 * chroma_gain,
    }
    return CostResult(total=sum(terms.values()), semantic=False, terms=terms)
