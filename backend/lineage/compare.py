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
from lineage.plugins import image_cost, image_explain, noise
from lineage.types import CostResult, ImageData

SIBLING_UNCOVERED = 0.05  # each side leaves at least this fraction of the other uncovered
MIN_DIRECTION_MARGIN = 0.05  # below this the two directions are indistinguishable
# 0.02 -> 0.05 on 2026-10-18 (benchmark/margin_floor_experiment.py): wrong-parent claims on the synthetic runs
# 11 -> 8 of 268 pairs and on Gemini edits 3 -> 2 of 25, for about 3 points more abstention; the 0.02-0.05
# margin bucket was only 70% precise on synthetic chains and 0 of 2 on web memes, so claims there were not trustworthy.
SEMANTIC_RELATED = 0.80  # CLIP cosine at or above this = same subject, even if pixels differ
PHASH_RELATED = 14  # bits, fallback when CLIP is unavailable


def _term(res: CostResult, key: str) -> float:
    return float(res.terms.get(key, 0.0)) / max(config.WEIGHTS.get(key, 1.0), 1e-9)


def _similarity(a: ImageData, b: ImageData) -> tuple[str, float]:
    if a.embedding is not None and b.embedding is not None:
        return "clip_cosine", float(np.dot(a.embedding, b.embedding) / (np.linalg.norm(a.embedding) * np.linalg.norm(b.embedding)))
    return "phash_bits_equal", 64 - (a.phash ^ b.phash).bit_count()


def wilson_lower(correct: int, n: int, z: float = 1.96) -> float | None:
    """Lower bound of the 95% Wilson interval: what we can claim from n trials, not the raw ratio."""
    if n <= 0:
        return None
    p = correct / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return round(max(0.0, (centre - spread) / denom), 3)


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
    override_confidence: dict | None = None
    conflicts: list[str] = []
    unavailable: list[str] = []
    decisive: list[str] = []
    noise_report: dict | None = None
    caption_side: str | None = None
    rerendered = False
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
        elif min(_term(ab, "color_residual"), _term(ba, "color_residual")) > config.RERENDER_RESIDUAL:
            # Aligned, but every pixel differs even after the colour fit: a restyle, a background swap
            # or a generative re-draw. Resolution and coverage then say nothing about direction.
            verdict, relation = "inconclusive", "re-rendered copy: aligned, but every pixel differs"
            parent = child = None
            rerendered = True
            summary = (f"The two align, yet the residual after the best colour fit is {min(_term(ab, 'color_residual'), _term(ba, 'color_residual')):.3f} "
                       f"(genuine crops, filters and re-saves stay under {config.RERENDER_RESIDUAL}). One of them was re-rendered rather than "
                       "edited pixel by pixel, so the usual direction cues do not apply and no parent is claimed.")
        else:
            forward = ab.total < ba.total  # a -> b is the cheap direction
            parent, child = ("A", "B") if forward else ("B", "A")
            cheap, dear = (ab, ba) if forward else (ba, ab)
            # Which cues does the direction rest on? Drop each term in turn: if the direction
            # flips or falls inside the margin without it, that cue is decisive.
            for key in ("coverage", "color_residual", "blockiness", "resolution", "chroma", "entropy", "blobs", "caption_removed", "edit_ops"):
                ab_wo, ba_wo = ab.total - ab.terms.get(key, 0.0), ba.total - ba.terms.get(key, 0.0)
                if ((ab_wo < ba_wo) != forward) or abs(ab_wo - ba_wo) < MIN_DIRECTION_MARGIN:
                    decisive.append(key)
            noise_report = noise.noise_consistency(a if forward else b, b if forward else a)
            caption_like = bool(noise_report and noise_report.get("caption_like"))
            cap_on = (noise_report or {}).get("caption_on")  # "copy" = child side, "source" = parent side
            caption_side = (child if cap_on == "copy" else parent) if cap_on else None
            if decisive == ["blobs"] and not caption_like:
                # A compact region of content that one image has and the other lacks is symmetric:
                # an object added to the parent, or an object removed from it. Only a two-tone
                # (caption-like) region is the calibrated case. Say so instead of guessing.
                verdict, relation = "inconclusive", "content differs in one region: added or removed, pixels alone cannot tell which"
                summary = (f"The two align and differ only in a compact region ({(noise_report or {}).get('region_fraction', 0):.1%} of the frame). "
                           f"Reading it as content added gives {cheap.total:.3f} for {parent}→{child}; reading it as content removed gives "
                           f"{dear.total:.3f} the other way. Our calibration covers captions, not object add/remove, so no parent is claimed. "
                           "Compression history or a third version would settle it.")
                parent = child = None
            elif decisive == ["edit_ops"]:
                # The only thing separating the two directions is the count of detected edit
                # primitives (0.05 each). The synthetic runs never decide on that alone and real
                # generative edits got it wrong 2 of 3 times, so it is not a direction.
                verdict, relation = "inconclusive", "direction rests only on the number of detected edit operations"
                summary = (f"Both directions align and cost almost the same ({ab.total:.3f} vs {ba.total:.3f}); the difference is one "
                           "detected edit primitive, which is a tie-breaker, not evidence. No parent is claimed.")
                parent = child = None
            elif caption_side == parent and len(decisive) <= 1:
                # The side the cost calls the parent carries caption-like content the other lacks,
                # and the cost direction hangs on one cue. The caption-side cue has its own
                # benchmark record; if that record exists the cue decides, otherwise no claim.
                cue = calibration.get("caption_side") or {}
                conflicts.append(f"Pixel cost preferred {parent}→{child} by a single cue ({decisive[0] if decisive else 'small margin'}); "
                                 f"overridden by the caption-side cue (captions are added, rarely removed).")
                if cue.get("n"):
                    parent, child = child, parent
                    verdict, relation = "parent-child", f"{parent} is the parent of {child} (caption-side cue)"
                    override_confidence = {"bucket": "caption-side cue", "precision": wilson_lower(cue["correct"], cue["n"]), "n": cue["n"],
                                           "observed": round(cue["correct"] / cue["n"], 3), "source": cue.get("source")}
                    summary = (f"{child} carries achromatic, high-contrast text-like content in the changed region that {parent} does not. "
                               f"On the benchmark this cue pointed to the derived copy {cue['correct']}/{cue['n']} times; the pixel cost "
                               f"preferred the other direction by one weak cue, so the caption-side reading is used.")
                else:
                    verdict, relation = "inconclusive", f"{parent} carries caption-like content {child} lacks, against a one-cue cost direction"
                    summary = (f"The pixel cost prefers {parent}→{child} by a single cue, but {parent} has text-like content {child} lacks. "
                               "The readings conflict and the caption-side cue has no benchmark record yet, so no parent is claimed.")
                    parent = child = None
            else:
                verdict, relation = "parent-child", f"{parent} is the parent of {child}"
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
                          ("blobs", "detail erased"), ("caption_removed", "caption removed")):
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
        c2 = md.get("c2pa")
        if c2 and c2.get("present"):
            state = c2.get("validation_state") or "unknown"
            who = c2.get("issuer") or c2.get("claim_generator") or "unknown signer"
            add("Content Credentials (C2PA)", f"{label}: manifest {state}, signed by {who}" + (f" at {c2['signed_at']}" if c2.get("signed_at") else "")
                + (f"; actions: {', '.join(c2['actions'][:5])}" if c2.get("actions") else ""),
                "signed edit history" if state == "Valid" else "manifest present but not valid: treat as untrusted", "hint", "metadata")
        elif md.get("c2pa_manifest"):
            add("C2PA manifest", f"present on {label} (could not be parsed)", "signed provenance may exist", "hint", "metadata")
        if md.get("software"):
            add("EXIF software tag", f"{label}: {md['software']}", "hint only", "hint", "metadata")
    if registered and parent and len(decisive) == 1:
        conflicts.append(f"The direction rests on a single cue ({decisive[0]}); without it the direction would be undetermined.")
    if registered and parent:
        # conflicts among pixel cues: a cue that penalises the chosen direction
        cheap = ab if parent == "A" else ba
        for key in ("blockiness", "resolution", "chroma", "entropy", "blobs"):
            if _term(cheap, key) > 0:
                conflicts.append(f"{key} also penalises the chosen direction ({_term(cheap, key):.3f}); the other terms outweighed it.")

    # ---- AI-edit indicators (measured only) ------------------------------------------
    ai_indicators: list[str] = []
    if rerendered:
        ai_indicators.append("Aligned pair whose pixels all differ after the best colour fit: consistent with a generative "
                             "re-draw, restyle or background replacement. Not proof of AI use.")
    if registered and noise_report is not None:
        who = child or "the derived copy"
        if caption_side:
            add("caption-like content on one side only", f"{caption_side} has two-tone, achromatic, high-contrast content in the changed region; the other image does not",
                f"{caption_side} is the derived copy (captions are added, rarely removed)", "indicator")
        if noise_report.get("two_tone") is not None:
            add("changed-region colour structure", f"{noise_report['two_tone']:.0%} of the changed pixels fall in two colours"
                + (" (caption-like)" if noise_report.get("caption_like") else " (natural content)"), "indicator only", "indicator")
        if noise_report.get("measurable"):
            add("noise consistency of the changed region",
                f"high-pass noise inside the changed {noise_report['region_fraction']:.1%} of {who}: "
                f"{noise_report['noise_inside_changed']}, outside: {noise_report['noise_outside']} (ratio {noise_report['ratio']})",
                "indicator only, no direction", "indicator")
            if noise_report["break"]:
                how = "smoother" if noise_report["ratio"] < 1 else "noisier"
                ai_indicators.append(f"The region of {who} that differs from the other image is {how} than the rest of the frame "
                                     f"(noise ratio {noise_report['ratio']}). Generated fills and pasted content usually break noise "
                                     "consistency this way. Not proof of AI use.")
        else:
            unavailable.append("noise consistency (no local change region of usable size to measure)")
    if not registered and related_by_meaning:
        ai_indicators.append("Same subject, no pixel alignment: typical of generative re-rendering or heavy restyling. Not proof of AI use.")
    for label, meta in (("A", meta_a), ("B", meta_b)):
        c2 = (meta.get("metadata") or {}).get("c2pa") or {}
        if c2.get("generative_ai_assertions"):
            ai_indicators.append(f"{label} carries a {c2.get('validation_state', 'unverified')} Content Credentials manifest declaring "
                                 f"{', '.join(c2['generative_ai_assertions'])} (signed by {c2.get('issuer') or 'unknown'}).")
        elif c2.get("present"):
            ai_indicators.append(f"{label} carries a Content Credentials manifest ({c2.get('validation_state', 'unverified')}) with no generative-AI assertion.")

    confidence = confidence_for(margin, calibration) if (margin is not None and verdict == "parent-child") else {"bucket": None, "precision": None, "n": 0}
    if override_confidence is None and decisive == ["caption_removed"] and (calibration.get("caption_side") or {}).get("n"):
        # The margin buckets were calibrated on edit chains without this term; when the caption
        # term alone decides, the honest number is the caption-side cue's own benchmark record.
        cue = calibration["caption_side"]
        override_confidence = {"bucket": "caption-side cue", "precision": wilson_lower(cue["correct"], cue["n"]), "n": cue["n"],
                               "observed": round(cue["correct"] / cue["n"], 3), "source": cue.get("source")}
    if override_confidence is not None:
        confidence = override_confidence
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
        "noise": noise_report,
        "decisive_cues": decisive,
        "rerendered": rerendered,
        "caption_side": caption_side,
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
