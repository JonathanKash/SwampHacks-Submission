"""Idempotent downloader for the Lineage meme benchmark corpus.

Reads  benchmark/memes/manifest.json
Writes benchmark/memes/images/<family>/<file>           (skipped if already present and valid)
       benchmark/memes/manifest.resolved.json           (manifest + width/height/bytes/sha256/format per file)
       benchmark/memes/download_log.json                (per-URL status, failures with reason)

Usage:  python download.py [--only family-id[,family-id]] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError

HERE = Path(__file__).resolve().parent
IMAGES = HERE / "images"
MANIFEST = HERE / "manifest.json"
RESOLVED = HERE / "manifest.resolved.json"
LOG = HERE / "download_log.json"
INDEX = IMAGES / ".index.json"  # rel file -> url, so a cached file is reused only for the URL it came from

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 20
EXT_FOR_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "MPO": "jpg"}

session = requests.Session()
session.headers.update(HEADERS)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(data: bytes) -> dict:
    """Verify bytes open with Pillow and return metadata."""
    im = Image.open(io.BytesIO(data))
    im.load()
    return {"width": im.width, "height": im.height, "format": im.format, "mode": im.mode}


def fetch(url: str) -> tuple[bytes | None, str | None]:
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:  # network / timeout
        return None, f"request error: {e.__class__.__name__}: {e}"
    if r.status_code != 200:
        return None, f"http {r.status_code}"
    ct = r.headers.get("content-type", "")
    if "text/html" in ct or len(r.content) < 200:
        return None, f"not an image (content-type={ct!r}, bytes={len(r.content)})"
    return r.content, None


def resolve_item(item: dict, family_id: str, log: list, force: bool, index: dict) -> dict:
    """Download (if needed) + verify one manifest entry; returns the entry enriched with file metadata."""
    out = dict(item)
    rel = Path(item["file"])
    target = IMAGES / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {"family": family_id, "file": item["file"], "url": item["url"], "status": None}

    # idempotent: reuse any existing sibling with the same stem (extension may have been corrected)
    existing = None
    if not force:
        for cand in target.parent.glob(rel.stem + ".*"):
            if index.get(cand.relative_to(IMAGES).as_posix()) != item["url"]:
                continue  # file on disk came from a different URL (manifest was renumbered): refetch
            try:
                data = cand.read_bytes()
                meta = inspect(data)
                existing = (cand, data, meta)
                break
            except (UnidentifiedImageError, OSError):
                continue

    if existing:
        path, data, meta = existing
        entry["status"] = "cached"
    else:
        data, err = fetch(item["url"])
        if data is None:
            entry["status"] = "failed"
            entry["error"] = err
            log.append(entry)
            out["downloaded"] = False
            out["error"] = err
            return out
        try:
            meta = inspect(data)
        except (UnidentifiedImageError, OSError) as e:
            entry["status"] = "failed"
            entry["error"] = f"pillow cannot open: {e}"
            log.append(entry)
            out["downloaded"] = False
            out["error"] = entry["error"]
            return out
        ext = EXT_FOR_FORMAT.get(meta["format"], (meta["format"] or "bin").lower())
        path = target.with_suffix("." + ext)
        path.write_bytes(data)
        entry["status"] = "downloaded"
        time.sleep(0.15)

    out["file"] = path.relative_to(IMAGES).as_posix()
    index[out["file"]] = item["url"]
    out["downloaded"] = True
    out.update({"width": meta["width"], "height": meta["height"], "format": meta["format"], "bytes": len(data), "sha256": sha256_of(data)})
    entry.update({"file": out["file"], "bytes": len(data), "width": meta["width"], "height": meta["height"]})
    log.append(entry)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated family ids")
    ap.add_argument("--force", action="store_true", help="re-download even if a valid file exists")
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    IMAGES.mkdir(exist_ok=True)
    index: dict = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    log: list = []
    pruned: list = []
    resolved_families = []
    for fam in manifest["families"]:
        if only and fam["id"] not in only:
            continue
        rf = dict(fam)
        rf["original"] = resolve_item(fam["original"], fam["id"], log, args.force, index)
        rf["variants"] = [resolve_item(v, fam["id"], log, args.force, index) for v in fam["variants"]]
        for key in ("components", "related_not_derived"):
            if fam.get(key):
                rf[key] = [resolve_item(v, fam["id"], log, args.force, index) for v in fam[key]]
        # prune files no longer referenced by the manifest (everything is re-downloadable)
        keep = {rf["original"].get("file")} | {v.get("file") for v in rf["variants"]}
        for key in ("components", "related_not_derived"):
            keep |= {v.get("file") for v in rf.get(key, [])}
        fam_dir = IMAGES / fam["id"]
        if fam_dir.exists():
            for f in fam_dir.iterdir():
                relf = f.relative_to(IMAGES).as_posix()
                if f.is_file() and relf not in keep:
                    f.unlink(); index.pop(relf, None); pruned.append(relf)
        INDEX.write_text(json.dumps(index, indent=0, sort_keys=True), encoding="utf-8")
        ok_v = sum(1 for v in rf["variants"] if v.get("downloaded"))
        rf["stats"] = {"original_ok": bool(rf["original"].get("downloaded")), "variants_ok": ok_v, "variants_total": len(rf["variants"]),
                       "complete": bool(rf["original"].get("downloaded")) and ok_v >= 6}
        resolved_families.append(rf)
        print(f"{fam['id']:32s} original={'ok ' if rf['stats']['original_ok'] else 'FAIL'} variants={ok_v}/{len(rf['variants'])}", flush=True)

    summary = {
        "families_total": len(resolved_families),
        "families_complete": sum(1 for f in resolved_families if f["stats"]["complete"]),
        "images_ok": sum(1 for e in log if e["status"] in ("downloaded", "cached")),
        "images_failed": sum(1 for e in log if e["status"] == "failed"),
        "pruned_stale_files": len(pruned),
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out = {k: v for k, v in manifest.items() if k != "families"}
    out["summary"] = summary
    out["families"] = resolved_families
    RESOLVED.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.write_text(json.dumps({"summary": summary, "failures": [e for e in log if e["status"] == "failed"], "entries": log}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
