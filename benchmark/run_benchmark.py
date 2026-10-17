"""Benchmark harness v2: honest numbers per corpus and per edit type.

Corpora:
  - nanobanana: benchmark/nanobanana/manifest.json  (real photo -> Gemini edit; truth: parent = source)
  - memes:      benchmark/memes/manifest.resolved.json (template/original + variants; truth: original is the root)
  - synthetic:  data/synthetic/<run>/truth.json (edit chains from the Phase 0 generator)

Metrics:
  pairwise direction accuracy (source vs edit must come out parent-child with the source as parent),
  verdict distribution (how often we say inconclusive/siblings/unrelated instead), tree root recovery
  (is the known original the candidate original of its family), per edit type / per variant kind,
  and calibration (does "N% precision" come out right about N% of the time, by bucket).
Failure cases are listed, not hidden. Usage:
  python benchmark/run_benchmark.py [--no-clip] [--corpus nanobanana|memes|synthetic|all] [--out benchmark/results.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lineage.compare import compare  # noqa: E402
from lineage.core.engine import Engine  # noqa: E402
from lineage.evidence import bucket_for, load_calibration  # noqa: E402
from lineage.plugins.image_fingerprint import ClipEmbedder, load_image_data  # noqa: E402


def _acc(c: int, n: int) -> float | None:
    return round(c / n, 3) if n else None


class Tally:
    def __init__(self) -> None:
        self.by_key: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.failures: list[dict] = []
        self.calib: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "n": 0})

    def add(self, key: str, metric: str, ok: bool) -> None:
        self.by_key[key][metric + "_n"] += 1
        self.by_key[key][metric + "_ok"] += int(ok)

    def summary(self) -> dict:
        out = {}
        for key, m in sorted(self.by_key.items()):
            row = {}
            for metric in sorted({k.rsplit("_", 1)[0] for k in m}):
                row[metric] = {"accuracy": _acc(m[metric + "_ok"], m[metric + "_n"]), "n": m[metric + "_n"]}
            out[key] = row
        return out


def pairwise_corpus(pairs: list[tuple[Path, Path, str]], embedder, tally: Tally, label: str) -> None:
    """pairs: (parent_path, child_path, edit_kind). The source must be judged the parent."""
    cache: dict[Path, object] = {}

    def data(p: Path):
        if p not in cache:
            cache[p] = load_image_data(p.name, p, embedder)
        return cache[p]

    for parent, child, kind in pairs:
        try:
            rep = compare(data(parent), data(child))
        except Exception as exc:  # unreadable file etc.
            tally.failures.append({"corpus": label, "kind": kind, "parent": str(parent), "child": str(child), "error": str(exc)[:200]})
            continue
        ok = rep["verdict"] == "parent-child" and rep["parent"] == "A"
        wrong_claim = rep["verdict"] == "parent-child" and rep["parent"] != "A"  # the error that matters most
        for key in (f"{label}/{kind}", f"{label}/_all"):
            tally.add(key, "direction", ok)
            tally.add(key, "wrong_parent_claimed", wrong_claim)
            tally.add(key, "abstained", rep["verdict"] != "parent-child")
        tally.add(f"{label}/{kind}", f"verdict={rep['verdict']}", True)
        if rep.get("caption_side"):  # the caption-side cue scored on its own: is the caption on the child?
            for key in (f"{label}/{kind}", f"{label}/_all"):
                tally.add(key, "caption_side_cue", rep["caption_side"] == "B")
        prec = rep["confidence"]["precision"]
        if rep["verdict"] == "parent-child" and rep["costs"]["margin"] is not None:
            b = tally.calib[bucket_for(rep["costs"]["margin"])]
            b["n"] += 1
            b["correct"] += int(ok)
        if not ok:
            tally.failures.append({"corpus": label, "kind": kind, "family": parent.parent.name, "parent": parent.name, "child": child.name,
                                   "verdict": rep["verdict"], "parent_claimed": rep["parent"], "costs": rep["costs"],
                                   "precision_claimed": prec, "summary": rep["summary"][:200]})


def tree_family(paths: list[Path], true_root: Path, embedder, tally: Tally, label: str, kinds: dict[str, str] | None = None) -> None:
    """All versions of one family in one pool: is the known original the candidate original?"""
    engine = Engine(use_clip=embedder is not None, embedder=embedder)
    for p in paths:
        try:
            engine.add_item(p.name, p)
        except Exception as exc:
            tally.failures.append({"corpus": label, "file": str(p), "error": str(exc)[:200]})
    if true_root.name not in engine.items:
        return
    result = engine.build_tree()
    root_ok = result.parent.get(true_root.name) is None
    tally.add(f"{label}/_family", "root_recovered", root_ok)
    # every variant should hang somewhere under the true root (direct child or deeper), and never above it
    for p in paths:
        if p.name == true_root.name or p.name not in engine.items:
            continue
        cur, under_root = result.parent.get(p.name), False
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            if cur == true_root.name:
                under_root = True
                break
            cur = result.parent.get(cur)
        kind = (kinds or {}).get(p.name, "variant")
        tally.add(f"{label}/{kind}", "under_true_original", under_root)
        tally.add(f"{label}/_all", "under_true_original", under_root)
        if not under_root:
            tally.failures.append({"corpus": label, "family": true_root.parent.name, "file": p.name, "kind": kind,
                                   "placed_under": result.parent.get(p.name), "note": "not a descendant of the known original"})


def run_nanobanana(embedder, tally: Tally) -> None:
    base = ROOT / "benchmark" / "nanobanana"
    mf = base / "manifest.json"
    if not mf.exists():
        print("nanobanana: no manifest yet")
        return
    data = json.loads(mf.read_text(encoding="utf-8"))
    pairs = []
    for fam in data.get("families", []):
        src = base / "sources" / fam["source"]["file"]
        if not src.exists():
            src = ROOT / "data" / "seeds" / fam["source"]["file"]
        for e in fam.get("edits", []):
            child = base / e["file"]
            if src.exists() and child.exists():
                pairs.append((src, child, e["edit"]))
    print(f"nanobanana: {len(pairs)} source/edit pairs")
    pairwise_corpus(pairs, embedder, tally, "nanobanana")
    # family trees: source + all its edits
    for fam in data.get("families", []):
        src = base / "sources" / fam["source"]["file"]
        if not src.exists():
            src = ROOT / "data" / "seeds" / fam["source"]["file"]
        members = [src] + [base / e["file"] for e in fam.get("edits", []) if (base / e["file"]).exists()]
        if src.exists() and len(members) > 1:
            tree_family(members, src, embedder, tally, "nanobanana", {(base / e["file"]).name: e["edit"] for e in fam.get("edits", [])})


def run_memes(embedder, tally: Tally) -> None:
    base = ROOT / "benchmark" / "memes"
    mf = base / "manifest.resolved.json"
    if not mf.exists():
        mf = base / "manifest.json"
    if not mf.exists():
        print("memes: no manifest yet")
        return
    data = json.loads(mf.read_text(encoding="utf-8"))
    fams = 0
    for fam in data.get("families", []):
        orig = base / fam["original"]["file"] if not str(fam["original"].get("file", "")).startswith("images/") else base / fam["original"]["file"]
        if not orig.exists():
            orig = base / "images" / fam["original"]["file"]
        variants = []
        kinds = {}
        for v in fam.get("variants", []):
            p = base / v["file"]
            if not p.exists():
                p = base / "images" / v["file"]
            if p.exists():
                variants.append(p)
                kinds[p.name] = v.get("kind", "variant")
        if not orig.exists() or not variants:
            continue
        fams += 1
        pairwise_corpus([(orig, v, kinds[v.name]) for v in variants], embedder, tally, "memes")
        tree_family([orig] + variants, orig, embedder, tally, "memes", kinds)
    print(f"memes: {fams} families evaluated")


def run_synthetic(embedder, tally: Tally) -> None:
    for run in sorted((ROOT / "data" / "synthetic").glob("run*")):
        truth = json.loads((run / "truth.json").read_text(encoding="utf-8"))["items"]
        by_id = {i["id"]: i for i in truth}
        pairs = [(run / by_id[i["parent"]]["file"], run / i["file"], i["edit"] or "edit") for i in truth if i["parent"]]
        print(f"synthetic {run.name}: {len(pairs)} pairs")
        pairwise_corpus(pairs[:120], embedder, tally, f"synthetic-{run.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--corpus", default="all", choices=["all", "nanobanana", "memes", "synthetic"])
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "results.json"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    embedder = None if args.no_clip else ClipEmbedder()
    tally = Tally()
    t0 = time.time()
    if args.corpus in ("all", "nanobanana"):
        run_nanobanana(embedder, tally)
    if args.corpus in ("all", "memes"):
        run_memes(embedder, tally)
    if args.corpus in ("all", "synthetic"):
        run_synthetic(embedder, tally)
    calib = load_calibration()
    results = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "phash-only" if args.no_clip else "clip",
        "seconds": round(time.time() - t0, 1), "calibration_runs": calib.get("runs", []),
        "metrics": tally.summary(),
        "calibration_check": {k: {"claimed_bucket": k, "observed_precision": _acc(v["correct"], v["n"]), "n": v["n"]} for k, v in tally.calib.items()},
        "failures": tally.failures,
    }
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n== results ({results['mode']}, {results['seconds']}s) ==")
    for key, row in results["metrics"].items():
        parts = [f"{m} {v['accuracy'] if v['accuracy'] is None else f'{v['accuracy']:.0%}'} (n={v['n']})" for m, v in row.items()]
        print(f"  {key:<34} " + "; ".join(parts))
    print("== calibration check (claimed bucket -> observed) ==")
    for k, v in results["calibration_check"].items():
        print(f"  {k:<22} observed {v['observed_precision']} (n={v['n']})")
    print(f"failures: {len(results['failures'])} -> {args.out}")


if __name__ == "__main__":
    main()
