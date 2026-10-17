"""Audit cases: create, batch upload, tree with summary, report, delete (no CLIP, tmp data dir)."""

from __future__ import annotations

import importlib
import io
import random

from lineage.edits import image_edits
from lineage.pool import Pool
from PIL import Image
from tests.conftest import synthetic_photo


def png(img: Image.Image, name: str) -> tuple[str, tuple[str, bytes, str]]:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ("files", (name, buf.getvalue(), "image/png"))


def test_case_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from lineage import config

    importlib.reload(config)
    import app as app_module

    importlib.reload(app_module)
    app_module.pool = Pool(tmp_path, use_clip=False)
    # Case pools share the demo pool's embedder (None here, so pHash-only).
    monkeypatch.setattr(app_module, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(app_module, "CASES_INDEX", tmp_path / "cases" / "index.json")
    app_module._case_pools.clear()
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    assert client.get("/api/cases").json() == {"cases": []}
    assert client.get("/api/cases/deadbeef/tree").status_code == 404

    case = client.post("/api/cases", json={"name": "Viral photo, Oct 16", "analyst": "J. Kash"}).json()
    assert case["name"] == "Viral photo, Oct 16" and case["items"] == 0 and case["analyst"] == "J. Kash"
    cid = case["id"]

    rng = random.Random(0)
    original = synthetic_photo(5)
    crop, _ = image_edits.crop(original, rng, fraction=0.6)
    dark, _ = image_edits.color_filter(crop, rng, kind="darker")
    files = [png(dark, "c.png"), png(original, "a.png"), png(crop, "b.png")]  # shuffled on purpose
    r = client.post(f"/api/cases/{cid}/items", files=files)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 3 and all(i["url"].startswith(f"/cases/{cid}/images/") for i in items)
    assert items[0]["params"]["filename"] == "c.png"
    assert items[0]["metadata"] == {"has_exif": False}

    tree = client.get(f"/api/cases/{cid}/tree").json()
    assert tree["mode"] == "audit"
    assert tree["summary"]["images"] == 3 and tree["summary"]["families"] == 1
    by_name = {n["params"]["filename"]: n for n in tree["nodes"]}
    assert by_name["a.png"]["root"] is True
    assert by_name["b.png"]["predicted_parent"] == by_name["a.png"]["id"]
    assert by_name["c.png"]["predicted_parent"] == by_name["b.png"]["id"]
    assert all(n["correct"] for n in tree["nodes"])  # no truth in audit mode
    assert client.get(f"/api/cases/{cid}/tree?since={tree['version']}").status_code == 204

    thumb = client.get(by_name["a.png"]["thumb"])
    assert thumb.status_code == 200 and thumb.headers["content-type"].startswith("image/")

    report = client.get(f"/api/cases/{cid}/report")
    assert report.status_code == 200 and "attachment" in report.headers["content-disposition"]
    body = report.json()
    assert body["originals"] == [by_name["a.png"]["id"]]
    assert len(body["decisions"]) == 2 and body["decisions"][0]["reasons"]

    page = client.get(f"/api/cases/{cid}/report.html")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "candidate original" in page.text and "data:image/jpeg;base64," in page.text and "a.png" in page.text
    assert "Evidence inventory" in page.text and "SHA-256" in page.text
    # tamper-evident footprint on every item
    fp = by_name["a.png"]["footprint"]
    assert len(fp["sha256"]) == 64 and fp["width"] > 0 and len(fp["phash"]) == 16
    # visual diff plate for a derived copy against its predicted source
    diff = client.get(f"/api/cases/{cid}/diff/{by_name['b.png']['id']}")
    assert diff.status_code == 200 and diff.headers["content-type"] == "image/png"
    assert diff.headers["x-diff-registered"] == "true" and int(diff.headers["x-diff-inliers"]) > 0
    assert client.get(f"/api/cases/{cid}/diff/{by_name['a.png']['id']}").status_code == 404  # roots have no source
    assert client.get("/api/report.html").status_code == 200

    assert client.get("/api/cases").json()["cases"][0]["items"] == 3
    assert client.delete(f"/api/cases/{cid}").json() == {"ok": True}
    assert client.get(f"/api/cases/{cid}/tree").status_code == 404
