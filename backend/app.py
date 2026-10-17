"""Lineage HTTP API (FastAPI).

Run from the repo root:  .venv/Scripts/python -m uvicorn app:app --app-dir backend --port 8000

Endpoints
  GET  /api/health
  GET  /api/pool                 all items (no true parents)
  GET  /api/random               one random item for the tablet
  GET  /api/tree                 nodes, predicted edges with labels, accuracy, newest_id, version
  GET  /api/tree?since=N         204 when nothing changed since version N (cheap 2 s polling)
  POST /api/items                multipart upload: file, parent_id?, edit?, params?(json)
  POST /api/edit                 json {parent_id, edit, params?}: server applies a menu edit
  POST /api/reset                clears the pool (needs ADMIN_TOKEN header if set in .env)
  /images/<file>, /thumbs/<id>.jpg   static
The engine never sees parent_id; it is stored only for the accuracy counter.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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


# Serve the built frontend (frontend/dist) at / when it exists; the API stays under /api.
_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
