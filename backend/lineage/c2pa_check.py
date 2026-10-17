"""Content Credentials (C2PA): read and validate an embedded manifest when one exists.

A valid, signed manifest is the strongest provenance evidence an image can carry, and
many generative tools attach one (with a "trained algorithmic media" digital source type).
We report what the library says; we never infer a manifest from EXIF or file names.
"""

from __future__ import annotations

import io
import json
from typing import Any


def inspect_c2pa(raw: bytes, mime: str = "image/jpeg") -> dict[str, Any] | None:
    """None when no manifest is embedded or the library is unavailable; otherwise a summary
    with the validation state, the active manifest's claim generator, signer and any
    generative-AI assertions."""
    try:
        import c2pa  # optional dependency
    except Exception:
        return None
    try:
        reader = c2pa.Reader(mime, stream=io.BytesIO(raw))
    except Exception:
        return None  # no manifest, unsupported container, or a corrupt one: nothing to report
    try:
        store = json.loads(reader.json())
    except Exception:
        return {"present": True, "validation_state": "unreadable"}
    active_id = store.get("active_manifest")
    manifest = (store.get("manifests") or {}).get(active_id, {})
    state = None
    for getter in ("get_validation_state",):
        try:
            state = str(getattr(reader, getter)())
        except Exception:
            pass
    sig = manifest.get("signature_info") or {}
    assertions = manifest.get("assertions") or []
    ai_sources = []
    actions = []
    for a in assertions:
        label = a.get("label", "")
        data = a.get("data") or {}
        if label.startswith("c2pa.actions"):
            for act in data.get("actions", []):
                actions.append(act.get("action"))
                src = act.get("digitalSourceType") or ""
                if "trainedAlgorithmicMedia" in src or "compositeWithTrainedAlgorithmicMedia" in src:
                    ai_sources.append(src.rsplit("/", 1)[-1])
    return {
        "present": True,
        "validation_state": state or store.get("validation_state"),
        "claim_generator": manifest.get("claim_generator") or manifest.get("claim_generator_info", [{}])[0].get("name"),
        "issuer": sig.get("issuer"),
        "signed_at": sig.get("time"),
        "actions": [x for x in actions if x][:12],
        "generative_ai_assertions": sorted(set(ai_sources)),
        "ingredients": len(manifest.get("ingredients") or []),
    }
