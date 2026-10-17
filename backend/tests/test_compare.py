"""Pairwise verdicts (compare module, API and CLI) on synthetic images, no CLIP."""

from __future__ import annotations

import importlib
import io
import json
import random

from lineage.compare import compare
from lineage.edits import image_edits
from lineage.pool import Pool
from PIL import Image
from tests.conftest import synthetic_photo, to_image_data


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def test_compare_parent_child_direction(photo, rng):
    child_img = image_edits.crop(photo, rng, fraction=0.6)[0]
    report = compare(to_image_data("A", photo), to_image_data("B", child_img), calibration={"buckets": {}})
    assert report["verdict"] == "parent-child" and report["parent"] == "A" and report["child"] == "B"
    assert report["costs"]["a_to_b"] < report["costs"]["b_to_a"]
    assert any(s["signal"] == "coverage" for s in report["signals"])
    assert report["reproducibility"]["weights_sha256_12"]
    # swapping the inputs swaps the labels, not the conclusion
    swapped = compare(to_image_data("B", child_img), to_image_data("A", photo), calibration={"buckets": {}})
    assert swapped["parent"] == "B"


def test_compare_siblings_unrelated_and_identical(photo, other_photo, rng):
    left = photo.crop((0, 0, 300, 360))  # two crops that do not contain each other
    right = photo.crop((180, 0, 480, 360))
    sib = compare(to_image_data("L", left), to_image_data("R", right), calibration={"buckets": {}})
    assert sib["verdict"] == "siblings" and sib["parent"] is None

    unrelated = compare(to_image_data("A", photo), to_image_data("B", other_photo), calibration={"buckets": {}})
    assert unrelated["verdict"] == "unrelated"

    same = compare(to_image_data("A", photo), to_image_data("A2", photo.copy()), calibration={"buckets": {}})
    assert same["verdict"] == "inconclusive" and "near-identical" in same["relation"]


def test_compare_api_with_uploads_and_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from lineage import config

    importlib.reload(config)
    import app as app_module

    importlib.reload(app_module)
    app_module.pool = Pool(tmp_path, use_clip=False)
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    original = synthetic_photo(4)
    child = image_edits.color_filter(image_edits.crop(original, random.Random(2), fraction=0.7)[0], random.Random(2), kind="darker")[0]
    # uploads: a real-camera-like JPEG parent at q92 and a re-saved child at q40 -> compression history agrees
    r = client.post("/api/compare", files={"a": ("a.jpg", jpeg_bytes(original, 92), "image/jpeg"),
                                           "b": ("b.jpg", jpeg_bytes(child, 40), "image/jpeg")})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["verdict"] == "parent-child" and rep["parent"] == "A"
    assert rep["plates"]["a_to_b"]["png"].startswith("data:image/png;base64,") and rep["plates"]["a_to_b"]["registered"]
    comp = next(s for s in rep["signals"] if s["signal"].startswith("compression history"))
    assert "favours A" in comp["direction"]
    assert rep["reproducibility"]["input_sha256"]["A"] and rep["conflicts"] == [] or isinstance(rep["conflicts"], list)

    # ids from the demo pool
    root = app_module.pool.add_image(original, None, None, source="seed")
    kid = app_module.pool.add_image(child, root["id"], "crop")
    r = client.post("/api/compare", data={"a_id": kid["id"], "b_id": root["id"]})
    assert r.status_code == 200 and r.json()["parent"] == "B"
    assert client.post("/api/compare", data={"a_id": "nope", "b_id": root["id"]}).status_code == 404
    assert client.post("/api/compare", data={"a_id": root["id"]}).status_code == 400


def test_cli_tree_place_and_compare(tmp_path):
    import lineage_cli

    folder = tmp_path / "set"
    folder.mkdir()
    original = synthetic_photo(6)
    crop = image_edits.crop(original, random.Random(3), fraction=0.65)[0]
    dark = image_edits.color_filter(crop, random.Random(3), kind="darker")[0]
    crop.save(folder / "b_crop.png")
    dark.save(folder / "c_dark.png")
    late_original = tmp_path / "found_original.png"
    original.save(late_original)

    out = tmp_path / "report.json"
    assert lineage_cli.main(["--no-clip", "tree", str(folder), "--json", "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["images"] == 2 and report["families"] == 1
    roots = [n["id"] for n in report["nodes"] if n["candidate_original"]]
    assert roots == ["b_crop.png"]

    # a late-arriving true original becomes the candidate original and explains the others
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert lineage_cli.main(["--no-clip", "place", str(late_original), "--against", str(folder), "--json"]) == 0
    placed = json.loads(buf.getvalue())
    assert placed["candidate_original"] is True and "b_crop.png" in placed["explains"]

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert lineage_cli.main(["--no-clip", "compare", str(late_original), str(folder / "b_crop.png"), "--json"]) == 0
    pair = json.loads(buf.getvalue())
    assert pair["verdict"] == "parent-child" and pair["parent"] == "A"
