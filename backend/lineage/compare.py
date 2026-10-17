"""Pairwise verdict: parent / child / siblings / unrelated / inconclusive, with the evidence.

This is the "Why is this the parent?" report for exactly two items. Every line in it
traces to a measured signal; when the signals disagree or the margin is too small the
verdict is "inconclusive" rather than a guess.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from lineage import config
from lineage.evidence import confidence_for, load_calibration
from lineage.plugins import image_cost, image_explain
from lineage.types import CostResult, ImageData

SIBLING_UNCOVERED = 0.05  # each side leaves at least this fraction of the other uncovered
MIN_DIRECTION_MARGIN = 0.02  # below this the two directions are indistinguishable
SEMANTIC_RELATED = 0.80  # CLIP cosine at or above this = same subject, even if pixels differ
PHASH_RELATED = 14  # bits, fallback when CLIP is unavailable


def _term(res: CostResult, key: str) -> float:
    return float(res.terms.get(key, 0.0)) / max(config.WEIGHTS.get(key, 1.0), 1e-9)


def _similarity(a: ImageData, b: ImageData) -> tuple[str, float]:
    if a.embedding is not None and b.embedding is not None:
        return "clip_cosine", float(np.dot(a.embedding, b.embedding) / (np.linalg.norm(a.embedding) * np.linalg.norm(b.embedding)))
    return "phash_bits_equal", 64 - (a.phash ^ b.phash).bit_count()


def _weights_hash() -> str:
    return hashlib.sha256(json.dumps(config.WEIGHTS, sort_keys=True).encode()).hexdigest()[:12]


def compare(a: ImageData, b: ImageData, meta_a: dict | None = None, meta_b: dict | None = None,
            tool_version: str = "dev", calibration: dict | None = None) -> dict:
    """Return the pairwise report. meta_* carry footprint/metadata hints (optional)."""
    calibration = calibration if calibration is not None else load_calibration()
    meta_a, meta_b = meta_a or {}, meta_b or {}
    ab = image_cost.cost(a, b)  # how cheaply is b made from a
    ba = image_cost.cost(b, a)
    sim_kind, sim = _similarity(a, b)
    registered = not ab.semantic and not ba.semantic
    signals: list[dict[str, Any]] = []
    conflicts: list[str] = []
    unavailable: list[str] = []
    if a.embedding is None or b.embedding is None:
        unavailable.append("CLIP embeddings (server in low-memory mode): semantic similarity falls back to pHash")
    for label, meta in (("A", meta_a), ("B", meta_b)):
        md = meta.get("metadata") or {}
        if not md.get("has_exif"):
            unavailable.append(f"EXIF metadata on {label} (absent or stripped)")
        if (meta.get("footprint") or {}).get("jpeg_quality") is None:
            unavailable.append(f"JPEG quantization tables on {label} (not a JPEG upload)")

    # ---- relation and direction -------------------------------------------------
    related_by_meaning = (sim >= SEMANTIC_RELATED) if sim_kind == "clip_cosine" else (sim >= 64 - PHASH_RELATED)
    if not registered:
        if related_by_meaning:
            verdict, relation = "inconclusive", "related by meaning only"
            summary = ("The two images show the same subject but their pixels do not align under any plausible "
                       "crop/rotation/scale. That is consistent with an AI edit, a heavy restyle or a re-creation; "
                       "the direction cannot be measured from pixels alone.")
        else:
            verdict, relation = "unrelated", "no shared content found"
            summary = "No keypoint alignment and low semantic similarity: these do not share a lineage."
        parent = child = None
        margin = None
    else:
        unc_ab, unc_ba = _term(ab, "coverage"), _term(ba, "coverage")  # fraction of target NOT covered
        margin = abs(ab.total - ba.total)
        if unc_ab > SIBLING_UNCOVERED and unc_ba > SIBLING_UNCOVERED:
            verdict, relation = "siblings", "each has content the other lacks"
            parent = child = None
            summary = (f"Aligned, but A leaves {unc_ba:.0%} of B uncovered and B leaves {unc_ab:.0%} of A uncovered: "
                       "neither contains the other, so they are most likely two copies of a common source.")
        elif margin < MIN_DIRECTION_MARGIN:
            verdict, relation = "inconclusive", "near-identical copies"
            parent = child = None
            summary = (f"Aligned and almost identical (cost {ab.total:.3f} vs {ba.total:.3f}); the difference is below "
                       f"the {MIN_DIRECTION_MARGIN} margin we trust, so the direction is not determinable.")
        else:
            forward = ab.total < ba.total  # a -> b is the cheap direction
            parent, child = ("A", "B") if forward else ("B", "A")
            verdict, relation = "parent-child", f"{parent} is the parent of {child}"
            cheap, dear = (ab, ba) if forward else (ba, ab)
            summary = (f"Producing {child} from {parent} costs {cheap.total:.3f}; producing {parent} from {child} would cost "
                       f"{dear.total:.3f} ({dear.total / max(cheap.total, 1e-6):.1f}× more). Read as: {image_explain.explain(cheap)}.")

    # ---- signal table ---------------------------------------------------------------
    def add(signal: str, found: str, direction: str, weight: float | str, kind: str = "pixel") -> None:
        signals.append({"signal": signal, "found": found, "direction": direction, "weight": weight, "kind": kind})

    add("keypoint registration", f"A→B inliers {ab.features.get('inliers', 0)}, B→A inliers {ba.features.get('inliers', 0)}",
        "both align" if registered else "no alignment", "gate")
    if registered:
        add("coverage", f"A covers {1 - _term(ab, 'coverage'):.0%} of B; B covers {1 - _term(ba, 'coverage'):.0%} of A",
            "toward the one that covers more" , config.WEIGHTS["coverage"])
        add("color fit residual", f"A→B {_term(ab, 'color_residual'):.4f}, B→A {_term(ba, 'color_residual'):.4f} (MSE, 0–1 scale)",
            "mostly symmetric", config.WEIGHTS["color_residual"])
        for key, name in (("blockiness", "JPEG grid energy lost"), ("resolution", "resolution gained"),
                          ("chroma", "color gained from gray"), ("entropy", "histogram entropy gained"),
                          ("blobs", "detail erased")):
            fa, fb = _term(ab, key), _term(ba, key)
            if fa > 0 or fb > 0:
                add(name, f"penalty A→B {fa:.3f}, B→A {fb:.3f}",
                    "against A→B" if fa > fb else "against B→A", config.WEIGHTS[key])
        ops_ab, ops_ba = ab.features.get("ops", []), ba.features.get("ops", [])
        add("edit operations detected", f"A→B: {', '.join(ops_ab) or 'none'}; B→A: {', '.join(ops_ba) or 'none'}",
            "fewer ops = more direct", f"{config.WEIGHTS['edit_op']} each")
    add("semantic similarity", f"{sim_kind} = {sim:.3f}", "relatedness only, no direction", "fallback", "semantic")

    # metadata hints: never evidence, shown with direction only when both sides have the value
    qa = (meta_a.get("footprint") or {}).get("jpeg_quality")
    qb = (meta_b.get("footprint") or {}).get("jpeg_quality")
    if qa is not None and qb is not None:
        add("compression history (estimated JPEG quality from quantization tables)", f"A ≈ q{qa}, B ≈ q{qb}",
            "parents are usually saved at higher quality" + (": favours A as parent" if qa > qb else ": favours B as parent" if qb > qa else ": equal"),
            "hint", "metadata")
        if parent and ((qa > qb and parent == "B") or (qb > qa and parent == "A")):
            conflicts.append("Compression history points the other way from the pixel verdict (the lower-quality file was judged the parent). Re-saving at higher quality does not restore detail, so the pixel verdict is kept, but treat this pair as a lead to verify.")
    fa_px = meta_a.get("footprint") or {}
    fb_px = meta_b.get("footprint") or {}
    if fa_px.get("width") and fb_px.get("width"):
        add("stored dimensions", f"A {fa_px['width']}×{fa_px['height']}, B {fb_px['width']}×{fb_px['height']}", "hint only", "hint", "metadata")
    for label, meta in (("A", meta_a), ("B", meta_b)):
        md = meta.get("metadata") or {}
        if md.get("c2pa_manifest"):
            add("C2PA manifest", f"present on {label} (signature not verified here)", "signed provenance exists", "hint", "metadata")
        if md.get("software"):
            add("EXIF software tag", f"{label}: {md['software']}", "hint only", "hint", "metadata")
    if registered and parent:
        # conflicts among pixel cues: a cue that penalises the chosen direction
        cheap = ab if parent == "A" else ba
        for key in ("blockiness", "resolution", "chroma", "entropy", "blobs"):
            if _term(cheap, key) > 0:
                conflicts.append(f"{key} also penalises the chosen direction ({_term(cheap, key):.3f}); the other terms outweighed it.")

    # ---- AI-edit indicators (measured only) ------------------------------------------
    ai_indicators: list[str] = []
    if not registered and related_by_meaning:
        ai_indicators.append("Same subject, no pixel alignment: typical of generative re-rendering or heavy restyling. Not proof of AI use.")
    for label, meta in (("A", meta_a), ("B", meta_b)):
        if (meta.get("metadata") or {}).get("c2pa_manifest"):
            ai_indicators.append(f"{label} carries a C2PA manifest; many AI tools attach one. Verify the signature with a C2PA tool.")

    confidence = confidence_for(margin, calibration) if (margin is not None and verdict == "parent-child") else {"bucket": None, "precision": None, "n": 0}
    detected_edit = None
    if registered and parent:
        cheap = ab if parent == "A" else ba
        detected_edit = (cheap.features.get("ops") or [None])[0]
    per_edit = (calibration.get("per_edit") or {}).get(detected_edit or "", None)
    benchmark = {"edit_type": detected_edit, "accuracy": round(per_edit["correct"] / per_edit["n"], 3) if per_edit and per_edit.get("n") else None,
                 "n": per_edit["n"] if per_edit else 0}

    return {
        "verdict": verdict,
        "relation": relation,
        "parent": parent,
        "child": child,
        "summary": summary,
        "confidence": confidence,
        "benchmark_for_edit_type": benchmark,
        "costs": {"a_to_b": round(ab.total, 4), "b_to_a": round(ba.total, 4), "margin": round(margin, 4) if margin is not None else None},
        "explain": {"a_to_b": image_explain.explain(ab), "b_to_a": image_explain.explain(ba)},
        "signals": signals,
        "conflicts": conflicts,
        "unavailable": unavailable,
        "ai_edit_indicators": ai_indicators,
        "limitations": [
            "Verdicts come from pixel measurements between these two files only; an earlier version outside them may exist.",
            "Near-lossless edits (small crops, mild filters) can leave the direction within the margin we do not trust; the report then says inconclusive.",
            "Metadata (EXIF, quantization tables, C2PA) is shown as a hint and never decides the verdict: it is easy to strip or forge.",
            "No AI-generation detector is used; only measurable indicators are listed.",
        ],
        "reproducibility": {"tool_version": tool_version, "weights_sha256_12": _weights_hash(),
                            "input_sha256": {"A": (meta_a.get("footprint") or {}).get("sha256"), "B": (meta_b.get("footprint") or {}).get("sha256")},
                            "calibration_runs": calibration.get("runs", [])},
    }
