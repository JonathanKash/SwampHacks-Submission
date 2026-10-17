"""Download a handful of CC0 (public domain) images from the Met Open Access API.

Usage:  python backend/scripts/fetch_seeds.py [--count 6] [--out data/seeds]
Writes  <out>/met_<objectID>.png and <out>/credits.json (for the README credits).
API docs: https://metmuseum.github.io/
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lineage import config  # noqa: E402

API = "https://collectionapi.metmuseum.org/public/collection/v1"
# search moved to v1.1 (paginated) on 2026-10-01; object lookups stay on v1.
SEARCH_API = "https://collectionapi.metmuseum.org/public/collection/v1.1"
# Varied, colourful, detailed subjects work best for ORB and CLIP.
QUERIES = ("landscape painting", "portrait", "still life", "cityscape", "garden", "animals")


def fetch(count: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    credits: list[dict] = []
    seen: set[int] = set()
    for query in QUERIES:
        if len(credits) >= count:
            break
        search = requests.get(
            f"{SEARCH_API}/search",
            params={"q": query, "isPublicDomain": "true", "hasImages": "true", "limit": 40, "offset": 0},
            timeout=30,
        ).json()
        for object_id in search.get("objectIDs") or []:
            if len(credits) >= count or object_id in seen:
                continue
            seen.add(object_id)
            meta = requests.get(f"{API}/objects/{object_id}", timeout=30).json()
            url = meta.get("primaryImageSmall") or meta.get("primaryImage")
            if not meta.get("isPublicDomain") or not url:
                continue
            try:
                img = Image.open(io.BytesIO(requests.get(url, timeout=60).content)).convert("RGB")
            except Exception as exc:  # bad download, skip it
                print(f"skip {object_id}: {exc}")
                continue
            if min(img.size) < 400:
                continue
            w, h = img.size
            scale = config.MAX_SIDE / max(w, h)
            if scale < 1:
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            path = out / f"met_{object_id}.png"
            img.save(path)
            credits.append(
                {
                    "file": path.name,
                    "title": meta.get("title"),
                    "artist": meta.get("artistDisplayName"),
                    "date": meta.get("objectDate"),
                    "url": meta.get("objectURL"),
                    "license": "CC0 (The Met Open Access)",
                }
            )
            print(f"saved {path.name}: {meta.get('title')!r} ({query})")
            break  # one image per query for variety
    (out / "credits.json").write_text(json.dumps(credits, indent=2))
    print(f"{len(credits)} seeds -> {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--out", type=Path, default=config.DATA_DIR / "seeds")
    args = parser.parse_args()
    fetch(args.count, args.out)
