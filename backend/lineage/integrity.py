"""Tamper-evident reports: a content hash plus an optional HMAC signature.

A newsroom or legal team that files a Lineage report needs to show later that it was
not altered. `stamp` adds `integrity` = {sha256 of the canonical body, hmac (if a signing
key is configured), signed_at}; `verify` recomputes both from a submitted report.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time


def _canonical(report: dict) -> bytes:
    body = {k: v for k, v in report.items() if k != "integrity"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def stamp(report: dict) -> dict:
    body = _canonical(report)
    digest = hashlib.sha256(body).hexdigest()
    key = os.getenv("REPORT_SIGNING_KEY", "")
    integrity = {"sha256": digest, "signed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "hmac_sha256": hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest() if key else None,
                 "algorithm": "sha256 over the canonical JSON body (sorted keys, no spaces), HMAC-SHA256 with the server key"}
    return {**report, "integrity": integrity}


def verify(report: dict) -> dict:
    integrity = report.get("integrity") or {}
    body = _canonical(report)
    digest = hashlib.sha256(body).hexdigest()
    key = os.getenv("REPORT_SIGNING_KEY", "")
    hash_ok = hmac.compare_digest(digest, str(integrity.get("sha256", "")))
    signature = integrity.get("hmac_sha256")
    if key and signature:
        sig_ok: bool | None = hmac.compare_digest(hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest(), str(signature))
    else:
        sig_ok = None  # unsigned report or no key on this server: cannot judge authorship
    return {"hash_matches": hash_ok, "signature_valid": sig_ok, "signed_at": integrity.get("signed_at"),
            "verdict": "intact and signed by this server" if hash_ok and sig_ok else
                       "intact, unsigned" if hash_ok and sig_ok is None else "ALTERED or not a Lineage report"}
