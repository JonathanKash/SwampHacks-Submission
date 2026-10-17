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
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lineage import config  # noqa: E402
from lineage.edits.image_edits import EDIT_TYPES, FILTER_KINDS  # noqa: E402
from lineage.pool import Pool  # noqa: E402

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
    return {"id": case_id, "name": meta["name"], "items": items, "created_at": meta["created_at"]}


class CaseCreate(BaseModel):
    name: str


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
        index[case_id] = {"name": name, "created_at": time.time(), "items": 0}
        _write_index(index)
    return _case_summary(case_id, index[case_id])


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
    images: list[tuple[Image.Image, str]] = []
    for upload in files:
        try:
            images.append((Image.open(io.BytesIO(upload.file.read())), upload.filename or "image"))
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
    report = case.report({"id": case_id, "name": meta["name"], "created_at": meta["created_at"]})
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="lineage-report-{case_id}.json"'})


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


# ---- demo pool ---------------------------------------------------------------------
class EditRequest(BaseModel):
    parent_id: str
    edit: str  # one of EDIT_TYPES or "restyle"
    params: dict = {}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "items": len(pool.engine.items), "version": pool.version}


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


@app.get("/api/report")
def demo_report():
    return JSONResponse(pool.report(), headers={"Content-Disposition": 'attachment; filename="lineage-report-demo.json"'})


@app.post("/api/items")
def upload(file: UploadFile = File(...), parent_id: str | None = Form(None),
           edit: str | None = Form(None), params: str | None = Form(None)) -> dict:
    try:
        img = Image.open(io.BytesIO(file.file.read()))
    except Exception as exc:  # not an image
        raise HTTPException(400, f"could not decode image: {exc}") from exc
    return pool.add_image(img, parent_id or None, edit, json.loads(params) if params else {})


@app.post("/api/edit")
def edit(req: EditRequest) -> dict:
    if req.parent_id not in pool.engine.items:
        raise HTTPException(404, "unknown parent_id")
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
