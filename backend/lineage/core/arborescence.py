"""Core 2/3: minimum spanning arborescence (Chu-Liu/Edmonds), forest-capable.

Problem: given directed edges src -> dst with costs (cost of "dst was derived
from src"), pick exactly one incoming edge per node so that the result is a set
of trees (no cycles) with minimum total cost. This is the minimum spanning
arborescence. It is the directed cousin of the minimum spanning tree, but the
greedy MST tricks (Kruskal/Prim) do not work because direction matters.

Forest trick: a virtual root gets an edge (virtual -> v, root_cost) to every
node v. A node that picks the virtual root is a tree root (parent None). So
unrelated families become separate trees, and an item with no cheap incoming
edge becomes its own root instead of being glued to a bad parent.

Chu-Liu/Edmonds in three steps:
1. For every non-root node keep only its cheapest incoming edge.
2. If those edges contain no cycle, they already form the optimal arborescence
   (each node pays the least it possibly could, and it is a valid tree).
3. Otherwise there is a cycle. Contract it into one super node. Every edge that
   enters the cycle is re-weighted: new_cost = cost - (cost of the cycle edge it
   would replace). Solve the smaller graph recursively, then expand: the one
   edge chosen to enter the super node breaks the cycle at its destination; all
   other cycle edges are kept.

The tests cross-check this implementation against networkx.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lineage.types import Edge

VIRTUAL_ROOT = "__virtual_root__"


@dataclass(frozen=True)
class _E:
    """An edge at one contraction level. `below` is the edge it came from at the
    level beneath (an original Edge at level 0), so expansion can trace back."""

    src: str
    dst: str
    cost: float
    below: object


def minimum_arborescence(
    nodes: Sequence[str], edges: Sequence[Edge], root_cost: float
) -> dict[str, str | None]:
    """Return parent[node] for every node in `nodes` (None = tree root).

    Rules:
    - Every node appears in the result exactly once.
    - The result is acyclic (following parent links always ends at None).
    - Among all parent assignments where each non-root node uses one of the
      given edges and roots pay root_cost, total cost is minimal.
    - Parallel edges (same src and dst) may appear; the cheapest is used.
    - Edges whose src or dst is not in `nodes`, and self loops, are ignored.
    - Ties are broken deterministically (first cheapest edge in sorted order).
    """
    nodes = list(nodes)
    if not nodes:
        return {}
    node_set = set(nodes)

    # Deduplicate parallel edges (keep the cheapest) and drop invalid ones.
    best: dict[tuple[str, str], Edge] = {}
    for e in edges:
        if e.src == e.dst or e.src not in node_set or e.dst not in node_set:
            continue
        if (e.src, e.dst) not in best or e.cost < best[(e.src, e.dst)].cost:
            best[(e.src, e.dst)] = e
    for n in nodes:  # the virtual root can be anyone's parent
        best[(VIRTUAL_ROOT, n)] = Edge(src=VIRTUAL_ROOT, dst=n, cost=root_cost)

    level0 = [_E(e.src, e.dst, e.cost, e) for (_, _), e in sorted(best.items())]
    chosen = _edmonds(VIRTUAL_ROOT, level0)  # node -> _E at level 0

    parent: dict[str, str | None] = {}
    for n in nodes:
        original: Edge = chosen[n].below  # type: ignore[assignment]
        parent[n] = None if original.src == VIRTUAL_ROOT else original.src
    return parent


def _edmonds(root: str, edges: list[_E]) -> dict[str, _E]:
    """Return {node: chosen incoming edge} for every non-root node reachable by
    the edges. Every non-root node is guaranteed an incoming edge here because
    the virtual root connects to all of them."""
    # Step 1: cheapest incoming edge per node.
    cheapest: dict[str, _E] = {}
    for e in edges:
        if e.dst == root or e.src == e.dst:
            continue
        if e.dst not in cheapest or e.cost < cheapest[e.dst].cost:
            cheapest[e.dst] = e

    # Step 2: look for a cycle among the chosen edges.
    cycle = _find_cycle(cheapest, root)
    if cycle is None:
        return cheapest

    # Step 3: contract the cycle into a super node and recurse.
    cycle_set = set(cycle)
    super_node = f"__cycle__{min(cycle)}__{len(edges)}"
    contracted: list[_E] = []
    for e in edges:
        in_src, in_dst = e.src in cycle_set, e.dst in cycle_set
        if in_src and in_dst:
            continue  # edge inside the cycle: disappears in the contraction
        if in_dst:
            # Entering the cycle: taking this edge means dropping the cycle edge
            # that currently feeds e.dst, so it only costs the difference.
            contracted.append(_E(e.src, super_node, e.cost - cheapest[e.dst].cost, e))
        elif in_src:
            contracted.append(_E(super_node, e.dst, e.cost, e))  # leaving the cycle
        else:
            contracted.append(_E(e.src, e.dst, e.cost, e))

    solved = _edmonds(root, contracted)  # keys are nodes at the contracted level

    # Expand: translate back to this level, then open the cycle.
    result: dict[str, _E] = {}
    entering: _E | None = None
    for node, e in solved.items():
        if node == super_node:
            entering = e.below  # type: ignore[assignment]
        else:
            result[node] = e.below  # type: ignore[assignment]
    assert entering is not None, "a cycle must be entered exactly once"
    for v in cycle:
        result[v] = cheapest[v]  # keep every cycle edge ...
    result[entering.dst] = entering  # ... except the one replaced by the entering edge
    return result


def _find_cycle(cheapest: dict[str, _E], root: str) -> list[str] | None:
    """Follow chosen parent links from each node; report the first cycle found."""
    state: dict[str, int] = {}  # 0 = visiting, 1 = done
    for start in cheapest:
        path: list[str] = []
        v = start
        while v != root and v in cheapest and state.get(v) is None:
            state[v] = 0
            path.append(v)
            v = cheapest[v].src
        if v != root and v in cheapest and state.get(v) == 0:
            return path[path.index(v):]  # v is on the current path: cycle found
        for p in path:
            state[p] = 1
    return None
