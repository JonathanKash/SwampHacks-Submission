"""Sweep a few cost weights and report tree accuracy on run1 (tuned) and run2/run3 (held out).
Only changes that improve run2+run3 without hurting run1 are worth keeping (CLAUDE.md rule).
Usage: python benchmark/weight_sweep.py [--no-clip]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lineage import config  # noqa: E402
from lineage.core.engine import Engine  # noqa: E402
from lineage.plugins.image_fingerprint import ClipEmbedder  # noqa: E402


def accuracy(run: Path, embedder, k: int) -> tuple[int, int]:
    truth = json.loads((run / "truth.json").read_text())["items"]
    engine = Engine(k=k, use_clip=embedder is not None, embedder=embedder)
    for i in truth:
        engine.add_item(i["id"], run / i["file"])
    result = engine.build_tree()
    correct = total = 0
    for i in truth:
        if i["parent"] is None and result.parent.get(i["id"]) is None:
            continue
        total += 1
        correct += int(result.parent.get(i["id"]) == i["parent"])
    return correct, total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clip", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    embedder = None if args.no_clip else ClipEmbedder()
    k = config.CANDIDATE_K_NO_CLIP if args.no_clip else config.CANDIDATE_K
    runs = [ROOT / "data" / "synthetic" / r for r in ("run1", "run2", "run3")]
    base = dict(config.WEIGHTS)
    grid = {
        "specificity": [0.01, 0.03, 0.06],
        "edit_op": [0.05, 0.1],
        "resolution": [0.5, 1.0],
        "blockiness": [1.0, 1.5],
    }
    keys = list(grid)
    print("setting".ljust(60), "run1   run2   run3   held-out")
    rows = []
    for values in itertools.product(*(grid[k_] for k_ in keys)):
        config.WEIGHTS.clear()
        config.WEIGHTS.update(base)
        config.WEIGHTS.update(dict(zip(keys, values)))
        # the cost caches are keyed by image content only, so clear them between settings
        from lineage.plugins import image_cost
        for attr in ("_feature_cache", "_stats_cache", "_sift_cache"):
            getattr(image_cost, attr, {}).clear()
        accs = [accuracy(r, embedder, k) for r in runs]
        pct = [c / t for c, t in accs]
        held = (accs[1][0] + accs[2][0]) / (accs[1][1] + accs[2][1])
        label = " ".join(f"{k_}={v}" for k_, v in zip(keys, values))
        rows.append((held, label, pct))
        print(label.ljust(60), " ".join(f"{p:.1%}" for p in pct), f"  {held:.1%}", flush=True)
    rows.sort(reverse=True)
    print("\nbest held-out:", rows[0][1], f"{rows[0][0]:.1%}", "| baseline:", next(r for r in rows if r[1] == " ".join(f"{k_}={base[k_]}" for k_ in keys))[0])


if __name__ == "__main__":
    main()
