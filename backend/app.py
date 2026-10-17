"""Lineage HTTP API (FastAPI).

Run from the repo root:  .venv/Scripts/python -m uvicorn app:app --app-dir backend --port 8010

Demo pool (the live hackathon demo; true parents known, accuracy shown)
  GET  /api/health
  GET  /api/pool                 all items (no true parents)
  GET  /api/random               one random item for the tablet
  GET  /api/tree[?since=N]       nodes, predicted edges with labels + evidence, accuracy, newest_id
  GET  /api/report               JSON report download for the demo pool
  POST /api/items                multipart upload: file, parent_id?, edit?, params?(json)
  POST /api/edit                 json {parent_id, edit, params?}: server applies a menu edit
  POST /api/reset                clears the pool (needs ADMIN_TOKEN header if set in .env)
  /images/<file>, /thumbs/<id>.jpg

Audit cases (industry mode; no ground truth, confidence from calibrated evidence)
  GET    /api/cases                      list
  POST   /api/cases {name}               create
  DELETE /api/cases/{id}
  POST   /api/cases/{id}/items           multipart, many `files`
  GET    /api/cases/{id}/tree[?since=N]  same shape as /api/tree + summary, mode="audit"
  GET    /api/cases/{id}/report          JSON report download
  /cases/{id}/images/<file>, /cases/{id}/thumbs/<id>.jpg

The engine never sees parent_id; it is stored only for the accuracy counter.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lineage import config  # noqa: E402
from lineage.edits.image_edits import EDIT_TYPES, FILTER_KINDS  # noqa: E402
from lineage.integrity import stamp, verify  # noqa: E402
from lineage.pool import Pool  # noqa: E402
from lineage.report_html import render_report  # noqa: E402


def _tool_version() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[1], timeout=5).stdout.strip() or "dev"
    except Exception:
        return "dev"


TOOL_VERSION = _tool_version()

app = FastAPI(title="Lineage")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
pool = Pool()
app.mount("/images", StaticFiles(directory=pool.images), name="images")
app.mount("/thumbs", StaticFiles(directory=pool.thumbs), name="thumbs")


# ---- audit cases -------------------------------------------------------------------
CASES_DIR = config.DATA_DIR / "cases"
CASES_INDEX = CASES_DIR / "index.json"
_cases_lock = threading.Lock()
_case_pools: dict[str, Pool] = {}


def _read_index() -> dict[str, dict]:
    return json.loads(CASES_INDEX.read_text(encoding="utf-8")) if CASES_INDEX.exists() else {}


def _write_index(index: dict[str, dict]) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    CASES_INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")


def _case_pool(case_id: str) -> Pool:
    if not re.fullmatch(r"[a-z0-9]{8}", case_id) or case_id not in _read_index():
        raise HTTPException(404, "unknown case")
    with _cases_lock:
        if case_id not in _case_pools:
            # Share the demo pool's CLIP model: one copy in RAM for every case.
            _case_pools[case_id] = Pool(CASES_DIR / case_id, embedder=pool.engine.embedder,
                                        url_prefix=f"/cases/{case_id}", mode="audit")
        return _case_pools[case_id]


def _case_summary(case_id: str, meta: dict) -> dict:
    items = len(_case_pools[case_id].engine.items) if case_id in _case_pools else meta.get("items", 0)
    return {"id": case_id, "name": meta["name"], "items": items, "created_at": meta["created_at"],
            "analyst": meta.get("analyst", "")}


class CaseCreate(BaseModel):
    name: str
    analyst: str | None = None


@app.get("/api/cases")
def list_cases() -> dict:
    index = _read_index()
    return {"cases": sorted((_case_summary(cid, m) for cid, m in index.items()), key=lambda c: -c["created_at"])}


@app.post("/api/cases")
def create_case(req: CaseCreate) -> dict:
    name = req.name.strip()[:80] or "Untitled case"
    with _cases_lock:
        index = _read_index()
        case_id = uuid.uuid4().hex[:8]
        index[case_id] = {"name": name, "created_at": time.time(), "items": 0, "analyst": (req.analyst or "").strip()[:80]}
        _write_index(index)
    return _case_summary(case_id, index[case_id])


@app.post("/api/cases/sample")
def create_sample_case() -> dict:
    """A ready-made case: one family (an original and its edited copies) copied from the demo pool,
    so visitors without their own versions can try the audit workspace."""
    import random as _random

    items = pool.store.list_items()
    roots = [i for i in items if i["true_parent"] is None]
    if not roots:
        raise HTTPException(409, "the demo pool is empty; seed it first")
    by_parent: dict[str, list[dict]] = {}
    for i in items:
        if i["true_parent"]:
            by_parent.setdefault(i["true_parent"], []).append(i)
    # Prefer a root with several descendants so the sample tree has something to show.
    def family(root_item: dict) -> list[dict]:
        out, stack = [], [root_item]
        while stack:
            cur = stack.pop()
            out.append(cur)
            stack.extend(by_parent.get(cur["id"], []))
        return out

    families = sorted((family(r) for r in roots), key=len, reverse=True)
    chosen = _random.choice(families[: max(1, len(families) // 2)])
    _random.shuffle(chosen)
    seed_name = str(chosen[0].get("params", {}).get("seed") or next(
        (c["params"].get("seed") for c in chosen if c.get("params", {}).get("seed")), "demo image"))
    created = create_case(CaseCreate(name=f"Sample: {len(chosen)} versions of {Path(seed_name).stem}", analyst="sample"))
    case = _case_pool(created["id"])
    images = []
    for item in chosen:
        path = pool.images / item["file"]
        images.append((Image.open(path), f"{item['edit'] or 'original'}-{item['id']}.png", path.read_bytes()))
    case.add_images(images)
    with _cases_lock:
        index = _read_index()
        index[created["id"]]["items"] = len(case.engine.items)
        _write_index(index)
    return _case_summary(created["id"], index[created["id"]])


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, x_admin_token: str | None = Header(None)) -> dict:
    expected = os.getenv("ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(403, "bad admin token")
    with _cases_lock:
        index = _read_index()
        if case_id not in index:
            raise HTTPException(404, "unknown case")
        del index[case_id]
        _write_index(index)
        existing = _case_pools.pop(case_id, None)
    if existing is not None:
        existing.reset()
    return {"ok": True}


@app.post("/api/cases/{case_id}/items")
def upload_case_items(case_id: str, files: list[UploadFile] = File(...)) -> dict:
    case = _case_pool(case_id)
    if len(files) > 40:
        raise HTTPException(400, "at most 40 images per upload")
    images: list[tuple[Image.Image, str, bytes]] = []
    for upload in files:
        try:
            raw = upload.file.read()
            images.append((Image.open(io.BytesIO(raw)), upload.filename or "image", raw))
        except Exception as exc:
            raise HTTPException(400, f"could not decode {upload.filename}: {exc}") from exc
    added = case.add_images(images)
    with _cases_lock:
        index = _read_index()
        if case_id in index:
            index[case_id]["items"] = len(case.engine.items)
            _write_index(index)
    return {"items": added}


@app.get("/api/cases/{case_id}/tree")
def case_tree(case_id: str, since: int | None = None):
    case = _case_pool(case_id)
    if since is not None and since >= case.version:
        return Response(status_code=204)
    return case.tree


@app.get("/api/cases/{case_id}/report")
def case_report(case_id: str):
    case = _case_pool(case_id)
    meta = _read_index()[case_id]
    report = case.report({"id": case_id, "name": meta["name"], "created_at": meta["created_at"], "analyst": meta.get("analyst", "")})
    report["tool"] = {"name": "Lineage", "version": TOOL_VERSION}
    report = stamp(report)
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="lineage-report-{case_id}.json"'})


@app.get("/api/cases/{case_id}/report.html")
def case_report_html(case_id: str):
    """Self-contained HTML report (print to PDF from the browser)."""
    case = _case_pool(case_id)
    meta = _read_index()[case_id]
    report = case.report({"id": case_id, "name": meta["name"], "created_at": meta["created_at"], "analyst": meta.get("analyst", "")})
    report["tool"] = {"name": "Lineage", "version": TOOL_VERSION}
    return HTMLResponse(render_report(report, case.thumbs, f"Lineage provenance report: {meta['name']}", case.diff_plates()))


MAX_BATCH_FILES = 40


@app.get("/api/cases/{case_id}/report.csv")
def case_report_csv(case_id: str):
    case = _case_pool(case_id)
    return Response(case.report_csv(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="lineage-ledger-{case_id}.csv"'})


@app.get("/api/report.csv")
def demo_report_csv():
    return Response(pool.report_csv(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="lineage-ledger-demo.csv"'})


def _diff_png(target_pool: Pool, item_id: str, other: str | None) -> Response:
    """Diff plate of item_id against its predicted source (or an explicit `other`)."""
    from lineage.diff import diff_plate, encode_png

    if item_id not in target_pool.engine.data:
        raise HTTPException(404, "unknown item")
    src = other or next((n["predicted_parent"] for n in target_pool.tree["nodes"] if n["id"] == item_id), None)
    if not src or src not in target_pool.engine.data:
        raise HTTPException(404, "item has no source to compare with")
    plate, info = diff_plate(target_pool.engine.data[src], target_pool.engine.data[item_id])
    headers = {"X-Diff-Registered": str(info["registered"]).lower(), "X-Diff-Inliers": str(info["inliers"]),
               "Cache-Control": "no-store"}
    return Response(encode_png(plate), media_type="image/png", headers=headers)


@app.get("/api/cases/{case_id}/diff/{item_id}")
def case_diff(case_id: str, item_id: str, other: str | None = None):
    return _diff_png(_case_pool(case_id), item_id, other)


@app.get("/api/diff/{item_id}")
def demo_diff(item_id: str, other: str | None = None):
    return _diff_png(pool, item_id, other)


@app.get("/cases/{case_id}/images/{file}", include_in_schema=False)
def case_image(case_id: str, file: str):
    path = _case_pool(case_id).images / Path(file).name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/cases/{case_id}/thumbs/{file}", include_in_schema=False)
def case_thumb(case_id: str, file: str):
    path = _case_pool(case_id).thumbs / Path(file).name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


# ---- pairwise compare: "Why is this the parent?" -------------------------------------
def _item_data_and_meta(target_pool: Pool, item_id: str) -> tuple:
    if item_id not in target_pool.engine.data:
        raise HTTPException(404, f"unknown item {item_id}")
    node = next((n for n in target_pool.tree["nodes"] if n["id"] == item_id), {})
    return target_pool.engine.data[item_id], {"footprint": node.get("footprint"), "metadata": node.get("metadata")}


def _upload_data_and_meta(upload: UploadFile, label: str) -> tuple:
    """Decode an ad-hoc upload into ImageData plus the same hints a pool item would carry."""
    import hashlib
    import tempfile

    from lineage.plugins.image_fingerprint import load_image_data
    from lineage.pool import c2pa_present, exif_hints, jpeg_quality_estimate

    raw = upload.file.read()
    try:
        img = Image.open(io.BytesIO(raw))
        hints = {**exif_hints(img), "c2pa_manifest": c2pa_present(raw)}
        width, height = img.size
    except Exception as exc:
        raise HTTPException(400, f"could not decode {upload.filename}: {exc}") from exc
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.convert("RGB").save(tmp, format="PNG")
        path = Path(tmp.name)
    try:
        data = load_image_data(f"{label}-{hashlib.sha256(raw).hexdigest()[:8]}", path, pool.engine.embedder)
    finally:
        path.unlink(missing_ok=True)
    meta = {"footprint": {"sha256": hashlib.sha256(raw).hexdigest(), "width": width, "height": height,
                          "bytes": len(raw), "jpeg_quality": jpeg_quality_estimate(raw)}, "metadata": hints}
    return data, meta


@app.post("/api/compare")
def compare_pair(a: UploadFile | None = File(None), b: UploadFile | None = File(None),
                 a_id: str | None = Form(None), b_id: str | None = Form(None), case: str | None = Form(None)) -> dict:
    """Two files, or two item ids from the demo pool (or a case): parent/child/siblings/unrelated/inconclusive."""
    from lineage.compare import compare

    target = _case_pool(case) if case else pool
    if a is not None:
        da, ma = _upload_data_and_meta(a, "A")
    elif a_id:
        da, ma = _item_data_and_meta(target, a_id)
    else:
        raise HTTPException(400, "provide file a or a_id")
    if b is not None:
        db, mb = _upload_data_and_meta(b, "B")
    elif b_id:
        db, mb = _item_data_and_meta(target, b_id)
    else:
        raise HTTPException(400, "provide file b or b_id")
    report = compare(da, db, ma, mb, tool_version=TOOL_VERSION)
    # Visual evidence inline (works for ad-hoc uploads too): source aligned onto copy, both ways.
    import base64

    from lineage.diff import diff_plate, encode_png

    plates = {}
    for key, (src, dst) in {"a_to_b": (da, db), "b_to_a": (db, da)}.items():
        plate, info = diff_plate(src, dst)
        plates[key] = {"png": "data:image/png;base64," + base64.b64encode(encode_png(plate)).decode("ascii"),
                       "registered": info["registered"], "inliers": info["inliers"]}
    report["plates"] = plates
    return report


# ---- text media (stateless demo of the second plug-in) -------------------------------
class TextVersion(BaseModel):
    id: str | None = None
    text: str


class TextTreeRequest(BaseModel):
    versions: list[TextVersion]


@app.post("/api/text/tree")
def text_tree(req: TextTreeRequest) -> dict:
    """Same core, different plug-in: paste several versions of a paragraph, get the tree."""
    from lineage.core.engine import Engine
    from lineage.evidence import build_evidence
    from lineage.plugins.text_media import TextMedia

    versions = [v for v in req.versions if v.text.strip()]
    if len(versions) < 2:
        raise HTTPException(400, "give at least two non-empty versions")
    if len(versions) > 40:
        raise HTTPException(400, "at most 40 versions")
    engine = Engine(media=TextMedia(), use_clip=False)
    ids: list[str] = []
    for i, v in enumerate(versions):
        item_id = (v.id or f"t{i + 1}")[:40]
        ids.append(item_id)
        engine.add_item(item_id, v.text)
    result = engine.build_tree()
    incoming: dict[str, dict] = {i: {} for i in ids}
    for (src, dst), res in engine.results.items():
        incoming[dst][src] = res
    children: dict[str, list[str]] = {i: [] for i in ids}
    for node, parent in result.parent.items():
        if parent:
            children[parent].append(node)

    def descendants(node: str) -> set[str]:
        out, stack = set(), list(children[node])
        while stack:
            n = stack.pop()
            if n not in out:
                out.add(n)
                stack.extend(children[n])
        return out

    # The precision table was calibrated on IMAGE edit chains; it does not transfer to
    # text margins, so text decisions show their raw margin instead of a precision.
    calibration = {"buckets": {}}
    nodes, edges = [], []
    for item_id, v in zip(ids, versions):
        pred = result.parent.get(item_id)
        reverse = engine.results.get((item_id, pred)) if pred else None
        ev = build_evidence(item_id, pred, incoming[item_id], reverse, engine.root_cost, calibration, descendants(item_id))
        nodes.append({"id": item_id, "text": v.text, "words": len(engine.data[item_id].words),
                      "predicted_parent": pred, "root": pred is None, "evidence": ev})
        if pred:
            res = engine.results[(pred, item_id)]
            short, full = engine.explain(res)
            edges.append({"src": pred, "dst": item_id, "label": short, "explain": full,
                          "cost": round(res.total, 4), "semantic": res.semantic, "evidence": ev})
    return {"mode": "text", "nodes": nodes, "edges": edges,
            "summary": {"versions": len(ids), "families": sum(1 for n in nodes if n["root"])},
            "note": "confidence is shown as the raw cost margin; the precision table is calibrated on image chains only"}


# ---- demo pool ---------------------------------------------------------------------
class EditRequest(BaseModel):
    parent_id: str
    edit: str  # one of EDIT_TYPES or "restyle"
    params: dict = {}


@app.get("/api/calibration")
def calibration() -> dict:
    """The empirical precision table behind every confidence figure (from scripts/calibrate.py)."""
    from lineage.evidence import MARGIN_BUCKETS, load_calibration

    cal = load_calibration()
    buckets = cal.get("buckets", {})
    ordered = [{"bucket": name, "min_margin": lower, **buckets.get(name, {"correct": 0, "n": 0})}
               for lower, name in MARGIN_BUCKETS]
    for row in ordered:
        row["precision"] = round(row["correct"] / row["n"], 3) if row["n"] else None
    return {"generated_at": cal.get("generated_at"), "runs": cal.get("runs", []), "buckets": ordered,
            "per_edit": cal.get("per_edit", {}), "root_cost": cal.get("root_cost"),
            "decisions": sum(r["n"] for r in ordered)}


def _lan_url() -> str | None:
    """Best-guess LAN address of this machine, so QR codes work when the page was opened via localhost."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))  # no packets are sent; this just picks the outbound interface
            ip = sock.getsockname()[0]
    except OSError:
        return None
    port = os.getenv("PORT", "8010")
    return f"http://{ip}:{port}"


LAN_URL = os.getenv("PUBLIC_URL") or _lan_url()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "items": len(pool.engine.items), "version": pool.version,
            "clip": pool.engine.embedder is not None, "lan_url": LAN_URL}


@app.get("/api/pool")
def list_pool() -> dict:
    return {"items": pool.items(), "edits": list(EDIT_TYPES) + ["restyle"], "filters": list(FILTER_KINDS)}


@app.get("/api/random")
def random_item() -> dict:
    item = pool.random_item()
    if item is None:
        raise HTTPException(404, "pool is empty")
    return item


@app.get("/api/tree")
def tree(since: int | None = None):
    if since is not None and since >= pool.version:
        return Response(status_code=204)
    return pool.tree


@app.post("/api/verify-report")
def verify_report(report: dict) -> dict:
    """Re-check a previously downloaded JSON report: hash intact? signed by this server?"""
    return verify(report)


@app.get("/api/report")
def demo_report():
    return JSONResponse(stamp({**pool.report(), "tool": {"name": "Lineage", "version": TOOL_VERSION}}), headers={"Content-Disposition": 'attachment; filename="lineage-report-demo.json"'})


@app.get("/api/report.html")
def demo_report_html():
    return HTMLResponse(render_report(pool.report(), pool.thumbs, "Lineage provenance report: live demo pool", pool.diff_plates()))


@app.post("/api/items")
def upload(file: UploadFile = File(...), parent_id: str | None = Form(None),
           edit: str | None = Form(None), params: str | None = Form(None)) -> dict:
    raw = file.file.read()
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception as exc:  # not an image
        raise HTTPException(400, f"could not decode image: {exc}") from exc
    return pool.add_image(img, parent_id or None, edit, json.loads(params) if params else {}, raw=raw)


_last_edit_by_ip: dict[str, float] = {}
EDIT_COOLDOWN_S = float(os.getenv("EDIT_COOLDOWN_S", "4"))


def _throttle(request: Request) -> None:
    """Phones joining via QR can tap Submit repeatedly; one edit per few seconds per client."""
    if EDIT_COOLDOWN_S <= 0:
        return
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    last = _last_edit_by_ip.get(ip, 0.0)
    if now - last < EDIT_COOLDOWN_S:
        raise HTTPException(429, f"One edit at a time: try again in {EDIT_COOLDOWN_S - (now - last):.0f}s")
    _last_edit_by_ip[ip] = now
    if len(_last_edit_by_ip) > 5000:
        _last_edit_by_ip.clear()


@app.post("/api/edit")
def edit(req: EditRequest, request: Request) -> dict:
    if req.parent_id not in pool.engine.items:
        raise HTTPException(404, "unknown parent_id")
    _throttle(request)
    if req.edit == "restyle":
        from lineage.edits.image_edits import restyle_local
        from lineage.plugins import gemini_restyle  # lazy: needs the API key

        style = req.params.get("style")
        try:
            out, params = gemini_restyle.restyle(pool.image_bytes(req.parent_id), style)
        except Exception as exc:
            # Image models need a billing-enabled key; keep the demo alive with an
            # offline stylization and say so in the stored params.
            if os.getenv("RESTYLE_LOCAL_FALLBACK", "true").lower() not in {"1", "true", "yes"}:
                raise HTTPException(502, f"restyle failed: {exc}") from exc
            print(f"[restyle] Gemini failed ({str(exc)[:120]}...); using local fallback")
            img = Image.open(io.BytesIO(pool.image_bytes(req.parent_id)))
            out, params = restyle_local(img, style)
            params["fallback_reason"] = str(exc)[:200]
        return pool.add_image(out, req.parent_id, "restyle", params)
    if req.edit not in EDIT_TYPES:
        raise HTTPException(400, f"edit must be one of {EDIT_TYPES} or 'restyle'")
    try:
        out, params = pool.apply_edit(req.parent_id, req.edit, req.params)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return pool.add_image(out, req.parent_id, req.edit, params)


def _check_admin(token: str | None) -> None:
    expected = os.getenv("ADMIN_TOKEN")
    if expected and token != expected:
        raise HTTPException(403, "bad admin token")


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str, x_admin_token: str | None = Header(None)) -> dict:
    """Moderation: remove an image from the demo pool (needs ADMIN_TOKEN header if set)."""
    _check_admin(x_admin_token)
    if not pool.remove(item_id):
        raise HTTPException(404, "unknown item")
    return {"ok": True, "items": len(pool.engine.items)}


@app.delete("/api/cases/{case_id}/items/{item_id}")
def delete_case_item(case_id: str, item_id: str, x_admin_token: str | None = Header(None)) -> dict:
    _check_admin(x_admin_token)
    if not _case_pool(case_id).remove(item_id):
        raise HTTPException(404, "unknown item")
    return {"ok": True}


@app.post("/api/reset")
def reset(x_admin_token: str | None = Header(None)) -> dict:
    expected = os.getenv("ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(403, "bad admin token")
    pool.reset()
    return {"ok": True}


# Serve the built frontend (frontend/dist) when it exists; the API stays under /api.
# Deep links (/edit, /tree, /audit) must return index.html so the React router can take over.
_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = _dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
