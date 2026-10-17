"""Phase 0 eval: run the engine on a synthetic run and report tree accuracy.

Usage: python backend/scripts/eval.py data/synthetic/<run> [--no-clip] [--real]

Reports:
1. Tree accuracy overall and per edit type (predicted parent == true parent;
   for true roots, "correct" means predicted as a root).
2. Per-cue direction table: for each true parent->child pair, does each cheap
   information-loss cue point the right way? This tests the core insight
   ("edits destroy information") independently of the cost's weighting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lineage import config  # noqa: E402
from lineage.core.engine import Engine  # noqa: E402


def pct(num: int, den: int) -> str:
    return f"{100.0 * num / den:5.1f}%" if den else "   n/a"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--no-clip", action="store_true", help="skip CLIP (faster, pHash only)")
    parser.add_argument("--k", type=int, default=config.CANDIDATE_K, help="candidates per item")
    parser.add_argument("--root-cost", type=float, default=config.ROOT_COST, help="cost of declaring an item a root")
    args = parser.parse_args()

    truth = json.loads((args.run / "truth.json").read_text())["items"]
    engine = Engine(use_clip=not args.no_clip, root_cost=args.root_cost, k=args.k)
    print(f"engine: clip={'off' if args.no_clip else 'on'}, k={args.k}, root_cost={args.root_cost}, items={len(truth)}")

    t0 = time.time()
    for item in truth:
        engine.add_item(item["id"], args.run / item["file"])
    t1 = time.time()
    tree = engine.build_tree()
    t2 = time.time()
    print(f"timing: fingerprints {t1 - t0:.1f}s, costs+tree {t2 - t1:.1f}s "
          f"({len(engine.results)} pair costs)")

    # ---- 1. tree accuracy ----------------------------------------------------
    correct_by_edit: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for item in truth:
        key = item["edit"] or "root"
        if item["edit"] == "filter":
            key = f"filter:{item['params'].get('kind')}"
        hit = tree.parent.get(item["id"]) == item["parent"]
        correct_by_edit[key][0] += int(hit)
        correct_by_edit[key][1] += 1
    non_root = [i for i in truth if i["parent"] is not None]
    hits = sum(tree.parent.get(i["id"]) == i["parent"] for i in non_root)
    print("\n== tree accuracy (predicted parent == true parent) ==")
    print(f"  overall (non-root items): {pct(hits, len(non_root))}  [{hits}/{len(non_root)}]")
    for key in sorted(correct_by_edit):
        c, n = correct_by_edit[key]
        print(f"  {key:<18} {pct(c, n)}  [{c}/{n}]")

    from lineage.core.candidates import top_k_candidates
    near = top_k_candidates(engine.fingerprints, engine.k)
    in_cand = sum(i["parent"] in near[i["id"]] or i["id"] in near[i["parent"]] for i in non_root)
    semantic_edges = sum(e.semantic for e in tree.edges.values())
    print(f"  true parent within top-{engine.k} candidates: {pct(in_cand, len(non_root))}; "
          f"semantic edges chosen: {semantic_edges}")

    # Where did wrong nodes attach? (same family vs other family vs root)
    by_id = {i["id"]: i for i in truth}
    wrong_kind: dict[str, int] = defaultdict(int)
    for item in non_root:
        pred = tree.parent.get(item["id"])
        if pred == item["parent"]:
            continue
        if pred is None:
            wrong_kind["predicted root"] += 1
        elif by_id[pred]["family"] != item["family"]:
            wrong_kind["other family"] += 1
        else:
            # same family: was it the reversed edge (child chosen as parent), an ancestor, or a sibling?
            true_parent = item["parent"]
            if by_id[pred]["parent"] == item["id"]:
                wrong_kind["own child (direction flipped)"] += 1
            elif by_id[true_parent]["parent"] == pred:
                wrong_kind["grandparent"] += 1
            elif by_id[pred]["parent"] == true_parent:
                wrong_kind["sibling"] += 1
            else:
                wrong_kind["other relative"] += 1
    if wrong_kind:
        print("  errors by kind:", dict(wrong_kind))

    # ---- 2. per-cue direction table -----------------------------------------
    print("\n== direction cues on true parent->child pairs (right / tie / wrong) ==")
    cues = {
        "resolution (child has <= pixels)": lambda p, c: (c.pixels < p.pixels) - (c.pixels > p.pixels),
        "blockiness (child >= parent)": lambda p, c: (c.blockiness > p.blockiness + 0.02)
        - (c.blockiness < p.blockiness - 0.02),
        "chroma (child <= parent)": lambda p, c: (c.chroma < p.chroma - 0.01) - (c.chroma > p.chroma + 0.01),
        "sharpness (child <= parent)": lambda p, c: (c.sharpness < p.sharpness * 0.95)
        - (c.sharpness > p.sharpness * 1.05),
        "levels (child <= parent)": lambda p, c: (c.levels < p.levels) - (c.levels > p.levels),
        "entropy (child <= parent)": lambda p, c: (c.entropy < p.entropy - 0.02) - (c.entropy > p.entropy + 0.02),
    }
    edits = sorted({(i["edit"] if i["edit"] != "filter" else f"filter:{i['params'].get('kind')}")
                    for i in non_root})
    header = f"  {'cue':<34}" + "".join(f"{e:>20}" for e in edits)
    print(header)
    for name, fn in cues.items():
        row = f"  {name:<34}"
        for edit in edits:
            tally = [0, 0, 0]  # right, tie, wrong
            for item in non_root:
                key = item["edit"] if item["edit"] != "filter" else f"filter:{item['params'].get('kind')}"
                if key != edit:
                    continue
                sign = fn(engine.stats[item["parent"]], engine.stats[item["id"]])
                tally[0 if sign > 0 else 1 if sign == 0 else 2] += 1
            row += f"{tally[0]:>7}/{tally[1]:>3}/{tally[2]:<3}      "
        print(row)
    print("\n(semantic distance is symmetric by construction and carries no direction.)")


if __name__ == "__main__":
    main()
