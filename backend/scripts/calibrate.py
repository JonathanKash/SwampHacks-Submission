"""Build calibration.json: empirical precision of parent decisions by cost margin.

Usage: python backend/scripts/calibrate.py data/synthetic/run1 data/synthetic/run2 [...]

For every item in every run we record the margin between the chosen cost and the
best alternative (another parent or "be a root"), and whether the decision was
right. Bucketed by margin, that gives "decisions with this margin were correct
N% of the time", which the API attaches to every edge as its confidence.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lineage import config  # noqa: E402
from lineage.core.engine import Engine  # noqa: E402
from lineage.evidence import CALIBRATION_PATH, bucket_for, build_evidence  # noqa: E402


def main(runs: list[Path]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # bucket names contain "≥"; Windows consoles default to cp1252
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "n": 0})
    per_edit: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "n": 0})
    for run in runs:
        truth = json.loads((run / "truth.json").read_text())["items"]
        engine = Engine()
        for item in truth:
            engine.add_item(item["id"], run / item["file"])
        tree = engine.build_tree()
        incoming: dict[str, dict] = defaultdict(dict)
        for (src, dst), res in engine.results.items():
            incoming[dst][src] = res
        children: dict[str, list[str]] = defaultdict(list)
        for node, parent in tree.parent.items():
            if parent is not None:
                children[parent].append(node)

        def descendants(node: str) -> set[str]:
            out, stack = set(), list(children[node])
            while stack:
                n = stack.pop()
                if n not in out:
                    out.add(n)
                    stack.extend(children[n])
            return out

        for item in truth:
            pred = tree.parent.get(item["id"])
            reverse = engine.results.get((item["id"], pred)) if pred else None
            ev = build_evidence(item["id"], pred, incoming[item["id"]], reverse, engine.root_cost, {"buckets": {}},
                                descendants(item["id"]))
            if ev["margin"] is None:
                continue
            hit = pred == item["parent"]
            b = buckets[bucket_for(ev["margin"])]
            b["n"] += 1
            b["correct"] += int(hit)
            e = per_edit[item["edit"] or "root"]
            e["n"] += 1
            e["correct"] += int(hit)
        print(f"{run.name}: {len(truth)} items")
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runs": [r.name for r in runs],
        "root_cost": config.ROOT_COST,
        "weights": config.WEIGHTS,
        "buckets": dict(buckets),
        "per_edit": dict(per_edit),
    }
    CALIBRATION_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"-> {CALIBRATION_PATH}")
    for name, b in out["buckets"].items():
        print(f"  {name:<20} {100 * b['correct'] / b['n']:5.1f}%  (n={b['n']})")


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]] or [config.DATA_DIR / "synthetic" / "run1", config.DATA_DIR / "synthetic" / "run2"]
    main(paths)
