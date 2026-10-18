"""Offline experiment: can wider SIFT coverage and softer inlier thresholds recover identify abstentions
without naming wrong families? Re-queries every held-out meme copy against the on-disk knowledge base
under several settings and prints correct / abstained / wrong per setting.
Usage: python benchmark/identify_recall_experiment.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lineage import config  # noqa: E402
from lineage.core.candidates import top_k_candidates  # noqa: E402
from lineage.plugins import image_cost  # noqa: E402
from lineage.plugins.image_fingerprint import load_image_data  # noqa: E402
from lineage.pool import Pool  # noqa: E402


def kb_pool() -> Pool:
    cases_dir = config.DATA_DIR / "cases"
    index = json.loads((cases_dir / "index.json").read_text(encoding="utf-8"))
    memes = sorted(((m.get("items", 0), cid) for cid, m in index.items() if "meme" in m.get("name", "").lower()), reverse=True)
    return Pool(cases_dir / memes[0][1], use_clip=False, mode="audit")


def place(pool: Pool, data, k: int, sift_top: int) -> dict:
    """Same logic as Pool.place but with tunable candidate count and SIFT coverage."""
    fps = {**pool.engine.fingerprints, "__q__": pool.engine.media.fingerprint(data)}
    cands = top_k_candidates(fps, k).get("__q__", [])
    scored = [(c, image_cost.cost(pool.engine.data[c], data, sift=False)) for c in cands]
    if all(r.semantic for _, r in scored):
        scored = [(c, image_cost.cost(pool.engine.data[c], data, sift=True)) for c in cands[:sift_top]] + scored[sift_top:]
    cid, res = min(scored, key=lambda t: t[1].total)
    if res.semantic or res.total >= config.IDENTIFY_MAX_COST_FRACTION * pool.engine.root_cost:
        return {"matched": False}
    node = next(n for n in pool.tree["nodes"] if n["id"] == cid)
    return {"matched": True, "family_id": (node.get("params") or {}).get("family_id")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    pool = kb_pool()
    in_kb = {(n.get("params") or {}).get("filename") for n in pool.tree["nodes"]}
    base = ROOT / "benchmark" / "memes"
    manifest = json.loads((base / "manifest.resolved.json").read_text(encoding="utf-8"))
    queries = [(f["id"], v) for f in manifest["families"] for v in f.get("variants", [])
               if v["file"] not in in_kb and (base / "images" / v["file"]).exists()]
    if args.limit:
        queries = queries[: args.limit]
    print(f"{len(queries)} held-out queries; knowledge base {len(pool.engine.items)} items")
    settings = [
        ("baseline k=16 sift_top=4 inliers=12", 16, 4, 12, 0.25),
        ("sift_top=16", 16, 16, 12, 0.25),
        ("sift_top=16 inliers=10", 16, 16, 10, 0.25),
        ("k=24 sift_top=24 inliers=10 ratio=0.2", 24, 24, 10, 0.20),
    ]
    data_cache = {}
    for name, k, sift_top, min_inl, ratio in settings:
        config.MIN_INLIERS, config.MIN_INLIER_RATIO = min_inl, ratio
        image_cost._reg_cache_clear() if hasattr(image_cost, "_reg_cache_clear") else None
        t0 = time.time()
        correct = wrong = abst = 0
        for fam_id, v in queries:
            p = base / "images" / v["file"]
            if p not in data_cache:
                data_cache[p] = load_image_data(p.name, p, None)
            out = place(pool, data_cache[p], k, sift_top)
            if not out["matched"]:
                abst += 1
            elif out["family_id"] == fam_id:
                correct += 1
            else:
                wrong += 1
        n = len(queries)
        print(f"{name:42s} correct {correct/n:.1%}  abstained {abst/n:.1%}  WRONG {wrong}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
