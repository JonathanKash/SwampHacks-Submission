"""Build the "Meme originals" audit case from benchmark/memes: every documented original plus a
few variants per family, with the provenance notes attached to each item. The case is the
knowledge base behind /identify ("which meme is this and where did it come from?").

Usage: .venv/Scripts/python backend/scripts/build_meme_case.py [--variants 2] [--no-clip]
Writes data/cases/<id>/ and registers the case in data/cases/index.json (the running server
picks it up on first access). Re-running replaces the previous meme case.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lineage import config  # noqa: E402
from lineage.pool import Pool  # noqa: E402
from PIL import Image  # noqa: E402

CASE_NAME = "Meme originals · 38 families"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=2, help="variants per family (prefer lowres then caption)")
    ap.add_argument("--no-clip", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    base = root / "benchmark" / "memes"
    manifest = json.loads((base / "manifest.resolved.json").read_text(encoding="utf-8"))
    cases_dir = config.DATA_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    index_path = cases_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    for cid, meta in list(index.items()):  # replace a previous build
        if meta.get("name") == CASE_NAME:
            index.pop(cid)
    case_id = uuid.uuid4().hex[:8]
    pool = Pool(cases_dir / case_id, use_clip=not args.no_clip, mode="audit", url_prefix=f"/api/cases/{case_id}")
    t0 = time.time()
    n = 0
    for fam in manifest["families"]:
        o = fam["original"]
        path = base / "images" / o["file"]
        if not path.exists():
            continue
        prov = {"family": fam["name"], "family_id": fam["id"], "role": "documented original",
                "source_url": o.get("source_url") or o.get("url"), "source_note": (o.get("source_note") or "")[:600],
                "date": o.get("date"), "is_true_source_photo": bool(o.get("is_true_source_photo")),
                "kym_url": fam.get("kym_url")}
        pool.add_image(Image.open(path), None, None, {"filename": o["file"], **prov}, source="web", rebuild=False, raw=path.read_bytes())
        n += 1
        picked = sorted(fam.get("variants", []), key=lambda v: {"lowres": 0, "caption": 1}.get(v.get("kind"), 2))[: args.variants]
        for v in picked:
            vp = base / "images" / v["file"]
            if not vp.exists():
                continue
            pool.add_image(Image.open(vp), None, None, {"filename": v["file"], "family": fam["name"], "family_id": fam["id"],
                                                         "role": f"variant ({v.get('kind')})", "source_url": v.get("url"),
                                                         "source_note": (v.get("note") or "")[:300]}, source="web", rebuild=False, raw=vp.read_bytes())
            n += 1
        print(f"{fam['id']}: {1 + len(picked)} items", flush=True)
    with pool.lock:
        pool._rebuild()
    index[case_id] = {"name": CASE_NAME, "created_at": time.time(), "items": len(pool.engine.items), "analyst": "benchmark/memes"}
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    s = pool.tree["summary"]
    print(f"case {case_id}: {n} items, {s['families']} families found, mean precision {s['mean_precision']}, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
