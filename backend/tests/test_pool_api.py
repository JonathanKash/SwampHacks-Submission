"""Pool + API smoke tests on a temporary data dir (no CLIP, pHash-only fingerprints)."""

from __future__ import annotations

import io
import random

import pytest
from PIL import Image

from lineage.pool import Pool
from tests.conftest import synthetic_photo


@pytest.fixture
def pool(tmp_path) -> Pool:
    return Pool(tmp_path, use_clip=False)


def test_pool_builds_tree_and_scores_accuracy(pool: Pool):
    root = pool.add_image(synthetic_photo(1), None, None, source="seed")
    crop_img, params = pool.apply_edit(root["id"], "crop", {"fraction": 0.6}, random.Random(0))
    child = pool.add_image(crop_img, root["id"], "crop", params)
    dark_img, params = pool.apply_edit(child["id"], "filter", {"kind": "darker"}, random.Random(0))
    grandchild = pool.add_image(dark_img, child["id"], "filter", params)

    tree = pool.tree
    assert tree["version"] == 3
    assert tree["newest_id"] == grandchild["id"]
    parents = {n["id"]: n["predicted_parent"] for n in tree["nodes"]}
    assert parents == {root["id"]: None, child["id"]: root["id"], grandchild["id"]: child["id"]}
    assert tree["accuracy"] == {"correct": 2, "total": 2, "pct": 100.0}
    labels = {e["dst"]: e["label"] for e in tree["edges"]}
    assert "crop" in labels[child["id"]]
    # Every decision carries its evidence: both directions, the runner-up, a margin, reasons.
    edge = next(e for e in tree["edges"] if e["dst"] == child["id"])
    ev = edge["evidence"]
    assert ev["measurements"]["cost_parent_to_child"] < ev["measurements"]["cost_child_to_parent"]
    assert ev["measurements"]["keypoint_inliers"] > 0
    assert ev["runner_up"] is not None and ev["margin"] is not None and ev["margin"] > 0
    assert any("keypoints" in r for r in ev["reasons"])
    root_node = next(n for n in tree["nodes"] if n["id"] == root["id"])
    assert root_node["evidence"]["reasons"]
    # no true parent anywhere in the public payload
    assert all("true_parent" not in n for n in tree["nodes"])


def test_pool_persists_and_reloads(tmp_path):
    pool = Pool(tmp_path, use_clip=False)
    root = pool.add_image(synthetic_photo(1), None, None, source="seed")
    img, params = pool.apply_edit(root["id"], "jpeg", {"quality": 10}, random.Random(0))
    pool.add_image(img, root["id"], "jpeg", params)
    costs_before = len(pool.engine.results)

    reloaded = Pool(tmp_path, use_clip=False)
    assert len(reloaded.engine.items) == 2
    assert len(reloaded.engine.results) == costs_before  # cost cache came from SQLite
    assert reloaded.tree["accuracy"]["correct"] == 1


def test_api_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib

    from lineage import config

    importlib.reload(config)
    import app as app_module

    importlib.reload(app_module)
    app_module.pool = Pool(tmp_path, use_clip=False)
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    assert client.get("/api/random").status_code == 404

    buf = io.BytesIO()
    synthetic_photo(2).save(buf, format="PNG")
    r = client.post("/api/items", files={"file": ("seed.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    root_id = r.json()["id"]

    r = client.post("/api/edit", json={"parent_id": root_id, "edit": "caption", "params": {"text": "hi"}})
    assert r.status_code == 200, r.text
    assert r.json()["edit"] == "caption"

    tree = client.get("/api/tree").json()
    assert len(tree["nodes"]) == 2 and len(tree["edges"]) == 1
    assert tree["edges"][0]["src"] == root_id
    assert client.get(f"/api/tree?since={tree['version']}").status_code == 204
    assert client.get("/api/random").status_code == 200
    assert client.post("/api/edit", json={"parent_id": "nope", "edit": "crop"}).status_code == 404
    assert client.post("/api/edit", json={"parent_id": root_id, "edit": "bogus"}).status_code == 400
