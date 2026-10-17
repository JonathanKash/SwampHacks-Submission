"""Measure /identify: for every meme variant that is NOT in the knowledge-base case, ask the running
server which family it belongs to. Reports family accuracy, abstentions, wrong families, tree
disagreements and latency. Usage: python benchmark/identify_eval.py [--server http://localhost:8010] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8010")
    ap.add_argument("--limit", type=int, default=0, help="max queries (0 = all held-out variants)")
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "identify_results.json"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    base = ROOT / "benchmark" / "memes"
    manifest = json.loads((base / "manifest.resolved.json").read_text(encoding="utf-8"))
    health = requests.get(f"{args.server}/api/health", timeout=30).json()
    if not health.get("identify_ready"):
        print("server has no identify case")
        return
    # which files are inside the knowledge base? ask the case tree for filenames
    cases = requests.get(f"{args.server}/api/cases", timeout=30).json()["cases"]
    case = max((c for c in cases if "meme" in c["name"].lower()), key=lambda c: c["items"])
    tree = requests.get(f"{args.server}/api/cases/{case['id']}/tree", timeout=120).json()
    in_kb = {(n.get("params") or {}).get("filename") for n in tree["nodes"]}
    rows = []
    for fam in manifest["families"]:
        for v in fam.get("variants", []):
            if v["file"] in in_kb or not (base / "images" / v["file"]).exists():
                continue
            rows.append((fam["id"], fam["name"], v))
    if args.limit:
        rows = rows[: args.limit]
    print(f"knowledge base {case['name']} ({case['items']} items); {len(rows)} held-out queries")
    tally = Counter()
    by_kind: dict[str, Counter] = {}
    times = []
    failures = []
    for fam_id, fam_name, v in rows:
        path = base / "images" / v["file"]
        t0 = time.time()
        with path.open("rb") as fh:
            r = requests.post(f"{args.server}/api/identify", files={"file": (path.name, fh, "image/jpeg")}, timeout=600).json()
        dt = time.time() - t0
        times.append(dt)
        kind = v.get("kind", "variant")
        k = by_kind.setdefault(kind, Counter())
        if not r.get("matched"):
            outcome = "abstained"
        else:
            got = (r["root"].get("params") or {}).get("family_id")
            outcome = "correct" if got == fam_id else "wrong_family"
            if r.get("tree_disagrees"):
                tally["tree_disagreed"] += 1
        tally[outcome] += 1
        k[outcome] += 1
        if outcome != "correct":
            failures.append({"family": fam_id, "file": v["file"], "kind": kind, "outcome": outcome,
                             "got": (r.get("root") or {}).get("params", {}).get("family") if r.get("matched") else None,
                             "reason": r.get("reason"), "strength": r.get("match_strength")})
    n = len(rows)
    out = {"knowledge_base": case["name"], "items": case["items"], "queries": n,
           "correct": tally["correct"], "abstained": tally["abstained"], "wrong_family": tally["wrong_family"],
           "tree_disagreed": tally["tree_disagreed"],
           "family_accuracy": round(tally["correct"] / n, 3) if n else None,
           "wrong_family_rate": round(tally["wrong_family"] / n, 3) if n else None,
           "median_latency_s": round(sorted(times)[len(times) // 2], 2) if times else None,
           "p90_latency_s": round(sorted(times)[int(len(times) * 0.9)], 2) if times else None,
           "by_kind": {k: dict(c) for k, c in by_kind.items()}, "failures": failures,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"family accuracy {out['family_accuracy']:.1%}  abstained {tally['abstained']}  wrong family {tally['wrong_family']}  "
          f"tree disagreed {tally['tree_disagreed']}  median {out['median_latency_s']}s  p90 {out['p90_latency_s']}s")
    for k, c in by_kind.items():
        print(f"  {k:<12} {dict(c)}")


if __name__ == "__main__":
    main()
