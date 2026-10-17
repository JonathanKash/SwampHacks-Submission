"""End-to-end smoke test against a running Lineage server (local or deployed).

Usage: python backend/scripts/smoke.py [http://localhost:8010]
Exercises: health, pool, random, a server-side edit, tree + evidence, report, an audit case
with a batch upload, the text tree, and the SPA routes. Exits non-zero on the first failure.
"""

from __future__ import annotations

import io
import sys
import time

import httpx
from PIL import Image, ImageDraw


def png(img: Image.Image, name: str) -> tuple[str, tuple[str, bytes, str]]:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ("files", (name, buf.getvalue(), "image/png"))


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        sys.exit(1)


def main(base: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    c = httpx.Client(base_url=base, timeout=300)
    h = c.get("/api/health").json()
    check(h.get("ok") is True, f"health ({h.get('items')} items)")
    for path in ["/", "/edit", "/tree", "/audit", "/text"]:
        r = c.get(path)
        check(r.status_code == 200 and "<div id=\"root\">" in r.text, f"SPA route {path}")

    if h.get("items", 0) > 0:
        item = c.get("/api/random").json()
        check("id" in item, "random item")
        check(c.get(item["thumb"]).status_code == 200, "thumbnail served")
        t0 = time.time()
        new = c.post("/api/edit", json={"parent_id": item["id"], "edit": "crop", "params": {"fraction": 0.7}}).json()
        check(new.get("edit") == "crop", f"server-side crop edit ({time.time() - t0:.1f}s)")
        tree = c.get("/api/tree").json()
        edge = next((e for e in tree["edges"] if e["dst"] == new["id"]), None)
        check(edge is not None and edge["evidence"]["reasons"], f"new edge with evidence: {edge['explain'] if edge else '-'}")
        check(c.get("/api/report").headers.get("content-disposition", "").startswith("attachment"), "demo report download")
    else:
        print("skip demo-pool checks (pool empty; run seed_pool.py)")

    # audit case: a textured synthetic original + crop + darker, shuffled. Texture
    # matters: flat fills give ORB too few keypoints to register.
    import random

    import numpy as np

    rng = np.random.default_rng(1)
    base_img = Image.fromarray(rng.integers(0, 256, size=(45, 60, 3), dtype=np.uint8)).resize((480, 360), Image.Resampling.BICUBIC)
    d = ImageDraw.Draw(base_img)
    r = random.Random(1)
    for _ in range(40):
        x0, y0 = r.randint(0, 440), r.randint(0, 320)
        d.rectangle((x0, y0, x0 + r.randint(10, 80), y0 + r.randint(10, 80)), fill=tuple(r.randint(0, 255) for _ in range(3)), outline="black")
    crop = base_img.crop((60, 40, 400, 320))
    dark = crop.point(lambda v: int(v * 0.6))
    case = c.post("/api/cases", json={"name": "smoke"}).json()
    r = c.post(f"/api/cases/{case['id']}/items", files=[png(dark, "c.png"), png(base_img, "a.png"), png(crop, "b.png")])
    check(r.status_code == 200, "audit batch upload")
    tree = c.get(f"/api/cases/{case['id']}/tree").json()
    by = {n["params"]["filename"]: n for n in tree["nodes"]}
    check(by["a.png"]["root"] and by["b.png"]["predicted_parent"] == by["a.png"]["id"]
          and by["c.png"]["predicted_parent"] == by["b.png"]["id"], "audit tree a -> b -> c")
    check(c.get(f"/api/cases/{case['id']}/report").status_code == 200, "audit report")
    check(c.delete(f"/api/cases/{case['id']}").json().get("ok") is True, "audit case deleted")

    t = c.post("/api/text/tree", json={"versions": [
        {"id": "long", "text": "The committee met on Monday to review the budget. It approved three new hires and a modest raise for staff. The chair thanked everyone for their patience."},
        {"id": "short", "text": "The committee met on Monday to review the budget. It approved three new hires and a modest raise for staff."},
        {"id": "reworded", "text": "The committee met Monday to go over the budget. It approved three new hires and a small raise for staff."},
    ]}).json()
    parents = {n["id"]: n["predicted_parent"] for n in t["nodes"]}
    check(parents == {"long": None, "short": "long", "reworded": "short"}, f"text tree {parents}")
    print("ALL OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010")
