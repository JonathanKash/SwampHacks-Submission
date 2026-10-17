"""Core 2/3: minimum spanning arborescence (Chu-Liu/Edmonds), forest-capable.

HAND-WRITTEN BY THE TEAM. Claude wrote only this interface, the docstrings and
backend/tests/test_arborescence.py. Do not let an AI fill in the bodies.

Problem: given directed edges src -> dst with costs (cost of "dst was derived
from src"), pick one incoming edge per node so that the result is a set of trees
(no cycles) with minimum total cost. This is the minimum spanning arborescence.

Forest trick: add a virtual root with an edge (virtual -> v, root_cost) to every
node v. A node that picks the virtual root is a tree root (parent None). Unrelated
families therefore become separate trees, and an item with no cheap incoming edge
becomes its own root instead of being glued to a bad parent.

Algorithm sketch (Chu-Liu/Edmonds):
1. For every non-root node keep its cheapest incoming edge.
2. If those edges form no cycle, done.
3. Otherwise contract each cycle into a super node, re-weight incoming edges by
   subtracting the cost of the edge they would replace inside the cycle, and
   recurse. Expand cycles afterwards, dropping exactly one cycle edge each.
"""

from __future__ import annotations

from collections.abc import Sequence

from lineage.types import Edge


def minimum_arborescence(
    nodes: Sequence[str], edges: Sequence[Edge], root_cost: float
) -> dict[str, str | None]:
    """Return parent[node] for every node in `nodes` (None = tree root).

    Rules:
    - Every node appears in the result exactly once.
    - The result is acyclic (following parent links always ends at None).
    - Among all such parent assignments where each non-root node uses one of the
      given edges and roots pay root_cost, total cost is minimal.
    - Parallel edges (same src and dst) may appear; use the cheapest.
    - Edges whose src or dst is not in `nodes` are ignored.
    - Self loops are ignored.
    - Ties may be broken arbitrarily but deterministically.
    """
    raise NotImplementedError
