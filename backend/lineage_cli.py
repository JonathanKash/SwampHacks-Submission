"""Lineage command line: the same engine, no server, usable at scale.

  lineage compare A.jpg B.jpg [--json]            pairwise verdict with the evidence report
  lineage tree FOLDER [--json] [--out report.json] reconstruct the lineage of every image in a folder
  lineage place IMAGE --against FOLDER [--json]   where does IMAGE land in an existing lineage
  lineage batch-compare FOLDER [--out pairs.csv]  every pair in a folder, as a CSV ledger

Add --no-clip on small machines (pHash-only candidate search). Reports record the tool
version, the weights hash and the SHA-256 of every input, so the same inputs reproduce the
same report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lineage.compare import compare  # noqa: E402
from lineage.core.engine import Engine  # noqa: E402
from lineage.evidence import build_evidence, load_calibration  # noqa: E402
from lineage.plugins.image_fingerprint import ClipEmbedder, load_image_data  # noqa: E402
from lineage.pool import c2pa_present, exif_hints, jpeg_quality_estimate  # noqa: E402
from PIL import Image  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def _version() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[1], timeout=5).stdout.strip() or "dev"
    except Exception:
        return "dev"


def _meta(path: Path) -> dict:
    raw = path.read_bytes()
    img = Image.open(io.BytesIO(raw))
    return {"footprint": {"sha256": hashlib.sha256(raw).hexdigest(), "width": img.size[0], "height": img.size[1],
                          "bytes": len(raw), "jpeg_quality": jpeg_quality_estimate(raw)},
            "metadata": {**exif_hints(img), "c2pa_manifest": c2pa_present(raw)}}


def _images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT)


def _engine(no_clip: bool) -> Engine:
    return Engine(use_clip=not no_clip, embedder=None if no_clip else ClipEmbedder())


def cmd_compare(args: argparse.Namespace) -> int:
    embedder = None if args.no_clip else ClipEmbedder()
    a, b = Path(args.a), Path(args.b)
    report = compare(load_image_data("A", a, embedder), load_image_data("B", b, embedder), _meta(a), _meta(b), _version())
    report["inputs"] = {"A": str(a), "B": str(b)}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(f"Verdict: {report['verdict']}  ({report['relation']})")
    if report["parent"]:
        print(f"Parent: {report['parent']} = {a if report['parent'] == 'A' else b}")
    c = report["confidence"]
    if c["precision"] is not None:
        label = "for this margin" if str(c["bucket"]).startswith("margin") else f"of the {c['bucket']}"
        print(f"Empirical precision {label}: {c['precision']:.0%} (n={c['n']}, {c['bucket']})")
    print(report["summary"])
    print("\nSignals:")
    for s in report["signals"]:
        print(f"  - {s['signal']}: {s['found']}  [{s['direction']}; weight {s['weight']}]")
    if report["conflicts"]:
        print("\nConflicts:")
        for x in report["conflicts"]:
            print(f"  - {x}")
    if report["unavailable"]:
        print("\nUnavailable:")
        for x in report["unavailable"]:
            print(f"  - {x}")
    if report["ai_edit_indicators"]:
        print("\nAI-edit indicators (measured only):")
        for x in report["ai_edit_indicators"]:
            print(f"  - {x}")
    print(f"\nReproducibility: tool {report['reproducibility']['tool_version']}, weights {report['reproducibility']['weights_sha256_12']}")
    return 0


def _tree_report(folder: Path, extra: Path | None, no_clip: bool) -> dict:
    engine = _engine(no_clip)
    paths = _images(folder)
    ids = {}
    for p in paths:
        ids[p.name] = p.name
        engine.add_item(p.name, p)
    if extra is not None:
        engine.add_item(f"QUERY:{extra.name}", extra)
    result = engine.build_tree()
    calibration = load_calibration()
    incoming: dict[str, dict] = {i: {} for i in engine.items}
    for (src, dst), res in engine.results.items():
        incoming[dst][src] = res
    children: dict[str, list[str]] = {i: [] for i in engine.items}
    for n, par in result.parent.items():
        if par:
            children[par].append(n)

    def descendants(n: str) -> set[str]:
        out, stack = set(), list(children[n])
        while stack:
            x = stack.pop()
            if x not in out:
                out.add(x)
                stack.extend(children[x])
        return out

    nodes = []
    for item_id in sorted(engine.items):
        par = result.parent.get(item_id)
        rev = engine.results.get((item_id, par)) if par else None
        ev = build_evidence(item_id, par, incoming[item_id], rev, engine.root_cost, calibration, descendants(item_id))
        label = engine.explain(engine.results[(par, item_id)])[1] if par else None
        nodes.append({"id": item_id, "parent": par, "edit": label, "candidate_original": par is None,
                      "margin": ev["margin"], "empirical_precision": ev["confidence"]["precision"], "reasons": ev["reasons"],
                      "sha256": hashlib.sha256(Path(folder / item_id).read_bytes()).hexdigest() if (folder / item_id).exists() else None})
    return {"tool_version": _version(), "folder": str(folder), "images": len(paths), "mode": "phash-only" if no_clip else "clip",
            "families": sum(1 for n in nodes if n["candidate_original"]), "nodes": nodes,
            "calibration_runs": calibration.get("runs", [])}


def cmd_tree(args: argparse.Namespace) -> int:
    report = _tree_report(Path(args.folder), None, args.no_clip)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(f"{report['images']} images, {report['families']} famil{'y' if report['families'] == 1 else 'ies'} ({report['mode']})")
    by_parent: dict[str | None, list[dict]] = {}
    for n in report["nodes"]:
        by_parent.setdefault(n["parent"], []).append(n)

    def show(parent: str | None, depth: int) -> None:
        for n in by_parent.get(parent, []):
            tag = "candidate original" if n["candidate_original"] else n["edit"]
            prec = f" · {n['empirical_precision']:.0%}" if n["empirical_precision"] is not None else ""
            print(f"{'  ' * depth}{n['id']}  [{tag}{prec}]")
            show(n["id"], depth + 1)

    show(None, 0)
    return 0


def cmd_place(args: argparse.Namespace) -> int:
    folder, image = Path(args.against), Path(args.image)
    report = _tree_report(folder, image, args.no_clip)
    qid = f"QUERY:{image.name}"
    node = next(n for n in report["nodes"] if n["id"] == qid)
    kids = [n["id"] for n in report["nodes"] if n["parent"] == qid]
    out = {"image": str(image), "against": str(folder), "placed_under": node["parent"], "edit": node["edit"],
           "explains": kids, "candidate_original": node["candidate_original"],
           "empirical_precision": node["empirical_precision"], "reasons": node["reasons"], "tool_version": report["tool_version"]}
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if out["candidate_original"] and kids:
        print(f"{image.name} is the NEW CANDIDATE ORIGINAL: it explains {len(kids)} existing image(s): {', '.join(kids)}")
    elif out["placed_under"]:
        print(f"{image.name} derives from {out['placed_under']}: {out['edit']}")
    else:
        print(f"{image.name} is unrelated to everything in {folder}")
    for r in out["reasons"]:
        print(f"  - {r}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    embedder = None if args.no_clip else ClipEmbedder()
    paths = _images(folder)
    data = {p.name: load_image_data(p.name, p, embedder) for p in paths}
    metas = {p.name: _meta(p) for p in paths}
    out = Path(args.out) if args.out else None
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["a", "b", "verdict", "parent", "cost_a_to_b", "cost_b_to_a", "margin", "empirical_precision", "explain_a_to_b"])
    names = list(data)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            r = compare(data[x], data[y], metas[x], metas[y], _version())
            parent = x if r["parent"] == "A" else y if r["parent"] == "B" else ""
            w.writerow([x, y, r["verdict"], parent, r["costs"]["a_to_b"], r["costs"]["b_to_a"], r["costs"]["margin"],
                        r["confidence"]["precision"], r["explain"]["a_to_b"]])
    if out:
        out.write_text(buf.getvalue(), encoding="utf-8")
        print(f"{len(names) * (len(names) - 1) // 2} pairs -> {out}")
    else:
        print(buf.getvalue())
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lineage", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-clip", action="store_true", help="pHash-only candidate search (low memory)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="pairwise verdict with evidence")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_compare)
    t = sub.add_parser("tree", help="reconstruct the lineage of a folder")
    t.add_argument("folder")
    t.add_argument("--json", action="store_true")
    t.add_argument("--out")
    t.set_defaults(fn=cmd_tree)
    p = sub.add_parser("place", help="where an image lands in an existing lineage")
    p.add_argument("image")
    p.add_argument("--against", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_place)
    b = sub.add_parser("batch-compare", help="every pair in a folder as CSV")
    b.add_argument("folder")
    b.add_argument("--out")
    b.set_defaults(fn=cmd_batch)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
