"""Evidence behind a parent decision, in numbers and in plain sentences.

A parent is never a guess: it is the cheapest of the measured directed costs
into a node, chosen by the arborescence. This module exposes exactly what was
measured for that decision (both directions, the runner-up, the margin) and
maps the margin to an empirical precision measured on the synthetic evaluation
runs (see scripts/calibrate.py, which writes calibration.json).
"""

from __future__ import annotations

import json
from pathlib import Path

from lineage import config
from lineage.types import CostResult

CALIBRATION_PATH = Path(__file__).with_name("calibration.json")

# Margin buckets (lower bound inclusive). Must match scripts/calibrate.py.
# Four buckets: with ~280 evaluated decisions, finer splits were non-monotone from sampling noise.
MARGIN_BUCKETS: tuple[tuple[float, str], ...] = (
    (0.30, "margin ≥ 0.30"),
    (0.05, "margin 0.05–0.30"),
    (0.02, "margin 0.02–0.05"),
    (0.0, "margin < 0.02"),
)


def bucket_for(margin: float) -> str:
    for lower, name in MARGIN_BUCKETS:
        if margin >= lower:
            return name
    return MARGIN_BUCKETS[-1][1]


def load_calibration() -> dict:
    if CALIBRATION_PATH.exists():
        return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    return {"buckets": {}, "runs": [], "note": "no calibration yet; run scripts/calibrate.py"}


def confidence_for(margin: float, calibration: dict) -> dict:
    """Empirical precision of decisions with a margin in the same bucket."""
    name = bucket_for(margin)
    stats = calibration.get("buckets", {}).get(name)
    # The same bucket measured on other corpora (e.g. web memes), so a claim is never shown
    # with only the number from the corpus it was tuned on.
    by_corpus = {}
    for corpus, rec in (calibration.get("corpora") or {}).items():
        b = (rec.get("buckets") or {}).get(name)
        if b and b.get("n"):
            by_corpus[corpus] = {"precision": round(b["correct"] / b["n"], 3), "n": b["n"]}
    if not stats or not stats.get("n"):
        return {"bucket": name, "precision": None, "n": 0, "by_corpus": by_corpus}
    return {"bucket": name, "precision": round(stats["correct"] / stats["n"], 3), "n": stats["n"], "by_corpus": by_corpus}


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def build_evidence(
    node_id: str,
    parent_id: str | None,
    incoming: dict[str, CostResult],
    reverse: CostResult | None,
    root_cost: float = config.ROOT_COST,
    calibration: dict | None = None,
    descendants: set[str] | None = None,
) -> dict:
    """Assemble the evidence for `node_id` having parent `parent_id`.

    incoming:    every measured cost INTO node_id, keyed by source id.
    reverse:     the cost of the opposite direction (node -> parent), if measured.
    descendants: ids below node_id in the final tree. They can look like cheap
                 parents locally, but choosing one would make the tree circular;
                 the arborescence rules them out, so they are not alternatives.
    """
    calibration = calibration if calibration is not None else load_calibration()
    descendants = descendants or set()
    ranked = sorted(incoming.items(), key=lambda kv: kv[1].total)
    chosen = incoming.get(parent_id) if parent_id else None
    chosen_cost = chosen.total if chosen else root_cost

    # Alternatives: every other measured, non-circular parent, plus "be a root".
    alternatives = [(src, res.total) for src, res in ranked if src != parent_id and src not in descendants]
    if parent_id is not None:
        alternatives.append(("__root__", root_cost))
    alternatives.sort(key=lambda kv: kv[1])
    runner_up_id, runner_up_cost = alternatives[0] if alternatives else (None, None)
    margin = (runner_up_cost - chosen_cost) if runner_up_cost is not None else None
    circular = [(src, res.total) for src, res in ranked if src in descendants and res.total < chosen_cost]

    reasons: list[str] = []
    measurements: dict[str, float | int | str | list[float]] = {}
    if chosen is not None and isinstance(chosen.features.get("reasons"), list):
        # Non-image media plug-ins supply their own measurement sentences.
        reasons.extend(str(r) for r in chosen.features["reasons"])
        for key in ("len_a", "len_b", "jaccard_words", "jaccard_shingles"):
            if key in chosen.features:
                measurements[key] = chosen.features[key]
        if reverse is not None:
            measurements["cost_parent_to_child"] = round(chosen.total, 4)
            measurements["cost_child_to_parent"] = round(reverse.total, 4)
            ratio = reverse.total / chosen.total if chosen.total > 1e-6 else float("inf")
            reasons.append(
                f"Producing this version from the parent costs {chosen.total:.3f}; producing the parent from this "
                f"version would cost {reverse.total:.3f}"
                + (f" ({ratio:.1f}× more)." if ratio != float("inf") else " (the forward cost is essentially zero).")
            )
    elif chosen is not None:
        f, t = chosen.features, chosen.terms
        w = config.WEIGHTS
        if chosen.semantic:
            cos = f.get("clip_cos")
            reasons.append(
                "The pixels no longer align with any pool image (too few consistent keypoints), so this "
                "edge was matched by meaning"
                + (f": CLIP cosine similarity {cos:.2f} with the chosen parent." if isinstance(cos, (int, float)) else ".")
            )
            if isinstance(cos, (int, float)):
                measurements["clip_cosine"] = round(float(cos), 3)
        else:
            inliers = int(f.get("inliers", 0))
            coverage_missing = t.get("coverage", 0.0) / w["coverage"]
            measurements["keypoint_inliers"] = inliers
            measurements["coverage_of_child_by_parent"] = round(1 - coverage_missing, 4)
            reasons.append(
                f"{inliers} matching keypoints align the parent onto this image; the warped parent covers "
                f"{_pct(1 - coverage_missing)} of it."
            )
            if reverse is not None and not reverse.semantic:
                rev_missing = reverse.terms.get("coverage", 0.0) / w["coverage"]
                measurements["coverage_of_parent_by_child"] = round(1 - rev_missing, 4)
                if rev_missing > 0.02:
                    reasons.append(
                        f"In the reverse direction this image would leave {_pct(rev_missing)} of the parent "
                        "uncovered: that information is simply not here."
                    )
            residual = t.get("color_residual", 0.0) / w["color_residual"]
            measurements["color_fit_residual_mse"] = round(float(residual), 5)
            gains = f.get("color_gain")
            if isinstance(gains, list) and len(gains) == 3:
                measurements["color_gain_rgb"] = [round(float(g), 3) for g in gains]
                reasons.append(
                    f"After a per-channel color fit (gains R {gains[0]:.2f}, G {gains[1]:.2f}, B {gains[2]:.2f}) "
                    f"the remaining pixel error is {residual:.4f} on a 0–1 scale."
                )
            ops = f.get("ops", [])
            ba, bb = f.get("blockiness_a"), f.get("blockiness_b")
            if "jpeg" in ops and isinstance(ba, (int, float)) and isinstance(bb, (int, float)):
                measurements["blockiness_parent"] = round(float(ba), 3)
                measurements["blockiness_child"] = round(float(bb), 3)
                reasons.append(f"8×8 JPEG block energy rose from {ba:.2f} in the parent to {bb:.2f} here.")
            added = f.get("added_blob_fraction")
            if "caption" in ops and isinstance(added, (int, float)):
                measurements["added_content_fraction"] = round(float(added), 4)
                reasons.append(f"Compact new content covering {_pct(added)} of the frame exists here but not in the parent.")
            angle = f.get("angle_deg")
            if "rotate" in ops and isinstance(angle, (int, float)):
                measurements["rotation_deg"] = round(float(angle), 2)
            area = f.get("area_ratio")
            if "crop" in ops and isinstance(area, (int, float)):
                measurements["area_ratio"] = round(float(area), 3)
        if reverse is not None:
            measurements["cost_parent_to_child"] = round(chosen.total, 4)
            measurements["cost_child_to_parent"] = round(reverse.total, 4)
            ratio = reverse.total / chosen.total if chosen.total > 1e-6 else float("inf")
            reasons.append(
                f"Producing this image from the parent costs {chosen.total:.3f}; producing the parent from this "
                f"image would cost {reverse.total:.3f}"
                + (f" ({ratio:.1f}× more)." if ratio != float("inf") else " (the forward cost is essentially zero).")
            )
    else:
        outside = [(src, res) for src, res in ranked if src not in descendants]
        if descendants:
            reasons.append(
                f"All {len(descendants)} relatives in this family are explained more cheaply from this image than "
                "it is from them, so it is the family's original."
            )
        if not ranked:
            reasons.append("No other image in the pool is a candidate relative, so this is treated as an original.")
        elif outside:
            src, res = outside[0]
            reasons.append(
                f"The cheapest unrelated candidate parent would cost {res.total:.3f}, more than the root threshold "
                f"{root_cost:.2f}, so nothing outside the family explains it."
            )

    if circular:
        src, cost_ = circular[0]
        reasons.append(
            f"A locally cheaper parent exists (cost {cost_:.3f}) but it is one of this image's own descendants; "
            "using it would make the tree circular, so the arborescence rejected it."
        )

    if margin is not None and runner_up_id is not None:
        label = "being an original" if runner_up_id == "__root__" else "the next-best parent"
        reasons.append(f"The alternative ({label}) costs {runner_up_cost:.3f}; margin {margin:.3f}.")
    confidence = confidence_for(margin, calibration) if margin is not None else {"bucket": None, "precision": None, "n": 0}
    if confidence["precision"] is not None:
        reasons.append(
            f"In our evaluation, decisions with this margin were correct {_pct(confidence['precision'])} of the time "
            f"(n = {confidence['n']})."
        )

    return {
        "chosen_cost": round(chosen_cost, 4),
        "terms": {k: round(v, 4) for k, v in (chosen.terms.items() if chosen else {})},
        "runner_up": {"id": runner_up_id, "cost": round(runner_up_cost, 4)} if runner_up_cost is not None else None,
        "margin": round(margin, 4) if margin is not None else None,
        "confidence": confidence,
        "measurements": measurements,
        "reasons": reasons,
    }
