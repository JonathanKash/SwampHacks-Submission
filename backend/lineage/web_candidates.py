"""Internet candidates: pull likely relatives of an image from the web into a case.

Two paths:
- add_by_url: the user already knows candidate URLs (a tweet, an article, a listing).
- reverse_image_search: a provider finds visually similar pages. SerpApi's Google Lens /
  reverse-image engines are supported behind SERPAPI_KEY; they need a PUBLIC image URL,
  so this works on the deployed server (PUBLIC_URL) and not on a laptop behind NAT.

Everything fetched is treated as untrusted input: size-capped, content-type checked,
decoded with Pillow before it enters the pool. Provenance (source URL, page title) is
kept on the item so the report can cite where each candidate came from.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import httpx
from PIL import Image

MAX_BYTES = 25 * 1024 * 1024
UA = {"User-Agent": "Lineage/1.0 (+https://github.com/JonathanKash/SwampHacks-Submission)"}


@dataclass
class WebCandidate:
    url: str
    title: str = ""
    source: str = ""
    provider: str = "manual"


def fetch_image(url: str, timeout: float = 30.0) -> tuple[Image.Image, bytes]:
    """Download one image safely; raises ValueError with a readable reason."""
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=UA) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code} for {url}")
            ctype = resp.headers.get("content-type", "")
            if not ctype.startswith("image/") and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                raise ValueError(f"not an image ({ctype or 'unknown type'}): {url}")
            chunks, total = [], 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError(f"image larger than {MAX_BYTES // (1024 * 1024)} MB: {url}")
                chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise ValueError(f"could not decode {url}: {exc}") from exc
    return img, raw


def reverse_image_search(public_image_url: str, limit: int = 12) -> list[WebCandidate]:
    """Visually similar images via SerpApi (Google Lens). Requires SERPAPI_KEY."""
    key = os.getenv("SERPAPI_KEY")
    if not key:
        raise PermissionError("SERPAPI_KEY is not set; reverse-image search is disabled on this server")
    params = {"engine": "google_lens", "url": public_image_url, "api_key": key}
    with httpx.Client(timeout=60, headers=UA) as client:
        data = client.get("https://serpapi.com/search.json", params=params).json()
    out: list[WebCandidate] = []
    for m in data.get("visual_matches", [])[: limit * 2]:
        img = m.get("original") or m.get("thumbnail")
        if img:
            out.append(WebCandidate(url=img, title=str(m.get("title", ""))[:140], source=str(m.get("link", "")), provider="serpapi:google_lens"))
        if len(out) >= limit:
            break
    return out
