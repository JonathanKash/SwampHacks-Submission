"""Tests for core/arborescence.py (our own Chu-Liu/Edmonds).

Every result is checked against the structural rules, small cases against a
brute-force optimum, and larger random graphs against networkx's implementation,
so the "minimum" claim is actually verified.
"""

from __future__ import annotations

import itertools
import random

import networkx as nx
import pytest
from lineage.core.arborescence import minimum_arborescence
from lineage.types import Edge


def E(src: str, dst: str, cost: float) -> Edge:
    return Edge(src=src, dst=dst, cost=cost)


def total_cost(parent: dict[str, str | None], edges: list[Edge], root_cost: float) -> float:
    best: dict[tuple[str, str], float] = {}
    for e in edges:
        best[(e.src, e.dst)] = min(best.get((e.src, e.dst), float("inf")), e.cost)
    return sum(root_cost if p is None else best[(p, n)] for n, p in parent.items())


def assert_valid_forest(parent: dict[str, str | None], nodes: list[str], edges: list[Edge]) -> None:
    assert set(parent) == set(nodes), "every node appears exactly once"
    allowed = {(e.src, e.dst) for e in edges}
    for node, p in parent.items():
        if p is not None:
            assert (p, node) in allowed, f"{p}->{node} is not a given edge"
    for node in nodes:  # following parents must terminate at a root
        seen = set()
        cur: str | None = node
        while cur is not None:
            assert cur not in seen, f"cycle through {cur}"
            seen.add(cur)
            cur = parent[cur]


def brute_force_optimum(nodes: list[str], edges: list[Edge], root_cost: float) -> float:
    """Enumerate every parent assignment; return the minimum valid total cost."""
    options = {n: [None] + sorted({e.src for e in edges if e.dst == n and e.src != n}) for n in nodes}
    best = float("inf")
    for choice in itertools.product(*(options[n] for n in nodes)):
        parent = dict(zip(nodes, choice))
        try:
            assert_valid_forest(parent, nodes, edges)
        except AssertionError:
            continue
        best = min(best, total_cost(parent, edges, root_cost))
    return best


# ---- basic shapes -------------------------------------------------------------

def test_simple_chain():
    nodes = ["a", "b", "c"]
    edges = [E("a", "b", 1), E("b", "c", 1), E("b", "a", 5), E("c", "b", 5), E("a", "c", 3)]
    parent = minimum_arborescence(nodes, edges, root_cost=10)
    assert parent == {"a": None, "b": "a", "c": "b"}


def test_direction_decided_by_asymmetric_cost():
    nodes = ["p", "c"]
    edges = [E("p", "c", 0.2), E("c", "p", 0.9)]
    assert minimum_arborescence(nodes, edges, root_cost=10) == {"p": None, "c": "p"}


def test_star_with_branches():
    nodes = ["r", "x", "y", "z"]
    edges = [E("r", "x", 1), E("r", "y", 1), E("y", "z", 1), E("x", "z", 2), E("z", "y", 0.5), E("x", "r", 4)]
    parent = minimum_arborescence(nodes, edges, root_cost=10)
    assert parent == {"r": None, "x": "r", "y": "r", "z": "y"}


def test_single_node_is_root():
    assert minimum_arborescence(["solo"], [], root_cost=1.0) == {"solo": None}


def test_empty():
    assert minimum_arborescence([], [], root_cost=1.0) == {}


# ---- cycles (the part that makes Edmonds necessary) ---------------------------

def test_greedy_cheapest_in_edges_form_a_cycle():
    # Cheapest incoming edges: b<-a (1), a<-b (1) form a cycle; must break it using r.
    nodes = ["r", "a", "b"]
    edges = [E("a", "b", 1), E("b", "a", 1), E("r", "a", 2), E("r", "b", 3)]
    parent = minimum_arborescence(nodes, edges, root_cost=100)
    assert_valid_forest(parent, nodes, edges)
    assert parent == {"r": None, "a": "r", "b": "a"}
    assert total_cost(parent, edges, 100) == pytest.approx(103)


def test_three_cycle_is_broken_optimally():
    nodes = ["r", "a", "b", "c"]
    edges = [
        E("a", "b", 1), E("b", "c", 1), E("c", "a", 1),  # 3-cycle, all cheap
        E("r", "a", 10), E("r", "b", 5), E("r", "c", 8),  # entering the cycle
    ]
    parent = minimum_arborescence(nodes, edges, root_cost=100)
    assert_valid_forest(parent, nodes, edges)
    # Best: enter at b (5), then b->c (1), c->a (1) = 7 (+100 for r).
    assert parent == {"r": None, "b": "r", "c": "b", "a": "c"}


# ---- forest behaviour via root_cost --------------------------------------------

def test_two_unrelated_families_become_two_trees():
    nodes = ["a1", "a2", "b1", "b2"]
    edges = [E("a1", "a2", 0.3), E("a2", "a1", 0.8), E("b1", "b2", 0.2), E("b2", "b1", 0.7),
             E("a1", "b1", 4.0), E("b1", "a1", 4.0)]  # cross-family edges are expensive
    parent = minimum_arborescence(nodes, edges, root_cost=3.5)
    assert parent == {"a1": None, "a2": "a1", "b1": None, "b2": "b1"}


def test_low_root_cost_makes_everything_a_root():
    nodes = ["a", "b"]
    edges = [E("a", "b", 1.0), E("b", "a", 1.0)]
    assert minimum_arborescence(nodes, edges, root_cost=0.5) == {"a": None, "b": None}


def test_node_with_no_incoming_edges_is_a_root():
    nodes = ["a", "b"]
    assert minimum_arborescence(nodes, [E("a", "b", 1.0)], root_cost=9) == {"a": None, "b": "a"}


# ---- edge hygiene ----------------------------------------------------------------

def test_parallel_edges_use_cheapest_and_self_loops_ignored():
    nodes = ["a", "b"]
    edges = [E("a", "b", 5.0), E("a", "b", 0.5), E("b", "a", 2.0), E("a", "a", 0.0)]
    parent = minimum_arborescence(nodes, edges, root_cost=9)
    assert parent == {"a": None, "b": "a"}
    assert total_cost(parent, edges, 9) == pytest.approx(9.5)


def test_edges_to_unknown_nodes_are_ignored():
    parent = minimum_arborescence(["a"], [E("ghost", "a", 0.0), E("a", "ghost", 0.0)], root_cost=1)
    assert parent == {"a": None}


# ---- optimality against brute force on random small graphs -----------------------

@pytest.mark.parametrize("seed", range(12))
def test_matches_brute_force_optimum(seed: int):
    rnd = random.Random(seed)
    nodes = [f"n{i}" for i in range(5)]
    edges = [
        E(s, d, round(rnd.uniform(0.1, 3.0), 3))
        for s in nodes for d in nodes if s != d and rnd.random() < 0.6
    ]
    root_cost = rnd.choice([1.0, 2.5, 10.0])
    parent = minimum_arborescence(nodes, edges, root_cost)
    assert_valid_forest(parent, nodes, edges)
    assert total_cost(parent, edges, root_cost) == pytest.approx(brute_force_optimum(nodes, edges, root_cost))


# ---- cross-check against networkx on larger random graphs ------------------------

def networkx_total(nodes: list[str], edges: list[Edge], root_cost: float) -> float:
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    for n in nodes:
        graph.add_edge("__root__", n, weight=root_cost)
    for e in edges:
        if e.src == e.dst:
            continue
        current = graph.get_edge_data(e.src, e.dst)
        if current is None or e.cost < current["weight"]:
            graph.add_edge(e.src, e.dst, weight=e.cost)
    tree = nx.minimum_spanning_arborescence(graph, attr="weight")
    return sum(d["weight"] for _, _, d in tree.edges(data=True))


@pytest.mark.parametrize("seed", range(10))
def test_matches_networkx_on_random_graphs(seed: int):
    rnd = random.Random(100 + seed)
    n = rnd.randint(15, 40)
    nodes = [f"v{i}" for i in range(n)]
    edges = [
        E(s, d, round(rnd.uniform(0.05, 5.0), 4))
        for s in nodes for d in nodes if s != d and rnd.random() < 0.25
    ]
    root_cost = rnd.choice([1.0, 3.5, 20.0])
    parent = minimum_arborescence(nodes, edges, root_cost)
    assert_valid_forest(parent, nodes, edges)
    assert total_cost(parent, edges, root_cost) == pytest.approx(networkx_total(nodes, edges, root_cost), abs=1e-6)


def test_chain_shaped_like_an_edit_family():
    # root -> a -> b -> c with reverse edges costing more, plus a few cross edges.
    nodes = ["root", "a", "b", "c", "d"]
    edges = [
        E("root", "a", 0.1), E("a", "root", 1.6), E("a", "b", 0.2), E("b", "a", 1.5),
        E("b", "c", 0.15), E("c", "b", 1.2), E("root", "b", 0.5), E("a", "c", 0.6),
        E("root", "d", 0.3), E("d", "root", 1.9), E("c", "d", 0.9),
    ]
    parent = minimum_arborescence(nodes, edges, root_cost=3.5)
    assert parent == {"root": None, "a": "root", "b": "a", "c": "b", "d": "root"}
