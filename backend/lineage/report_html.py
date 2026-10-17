"""Self-contained HTML provenance report (thumbnails inlined), for sharing or printing to PDF.

Newsroom and legal teams archive findings as documents, not as live dashboards, so
the report carries everything: the tree, every decision's measurements and reasons,
the method, and the calibration note. No external assets.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path


def _thumb_data_uri(thumbs_dir: Path, item_id: str) -> str:
    path = thumbs_dir / f"{item_id}.jpg"
    if not path.is_file():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def render_report(report: dict, thumbs_dir: Path, title: str = "Lineage provenance report",
                  plates: dict[str, bytes] | None = None) -> str:
    e = html.escape
    plates = plates or {}
    nodes = {n["id"]: n for n in report["items"]}
    thumbs = {nid: _thumb_data_uri(thumbs_dir, nid) for nid in nodes}
    children: dict[str | None, list[str]] = {}
    for n in report["items"]:
        children.setdefault(n.get("predicted_parent"), []).append(n["id"])
    decisions = {d["image"]: d for d in report["decisions"]}

    def node_block(nid: str, depth: int) -> str:
        n = nodes[nid]
        d = decisions.get(nid)
        img = f'<img src="{thumbs[nid]}" alt="">' if thumbs[nid] else ""
        name = e(str(n.get("params", {}).get("filename") or n.get("edit") or nid))
        head = (
            f"<strong>{name}</strong> <code>{e(nid)}</code>"
            + (" · <em>candidate original</em>" if n.get("root") else "")
        )
        body = ""
        if d:
            rows = "".join(
                f"<tr><th>{e(k.replace('_', ' '))}</th><td>{e(str(v))}</td></tr>"
                for k, v in d["measurements"].items()
            )
            reasons = "".join(f"<li>{e(r)}</li>" for r in d["reasons"])
            parent_name = e(str(nodes.get(d["parent"], {}).get("params", {}).get("filename") or d["parent"]))
            body = (
                f'<p class="reading">Derived from <strong>{parent_name}</strong>: {e(d["edit"])}. '
                f'Cost {d["cost"]:.3f}, margin {("—" if d["margin"] is None else f"{d["margin"]:.3f}")}, '
                f'empirical precision {_pct(d["empirical_precision"])}'
                + (" · matched by meaning" if d["semantic"] else "")
                + "</p>"
                f"<ul>{reasons}</ul><table>{rows}</table>"
            )
            if nid in plates:
                uri = "data:image/png;base64," + base64.b64encode(plates[nid]).decode("ascii")
                body += (f'<figure class="plate"><img src="{uri}" alt="visual diff plate">'
                         "<figcaption>Exhibit: source aligned onto this copy · this copy · residual after color fit "
                         "(brighter = more different; hatched = area the source cannot supply)</figcaption></figure>")
        else:
            reasons = "".join(f"<li>{e(r)}</li>" for r in n.get("evidence", {}).get("reasons", []))
            body = f"<ul>{reasons}</ul>"
        kids = "".join(node_block(c, depth + 1) for c in children.get(nid, []))
        return f'<section class="node" style="margin-left:{depth * 22}px">{img}<div>{head}{body}</div></section>{kids}'

    tree_html = "".join(node_block(r, 0) for r in children.get(None, []))
    inventory = "".join(
        f"<tr><td><code>{e(n['id'])}</code></td><td>{e(str(n.get('params', {}).get('filename') or n.get('edit') or ''))}</td>"
        f"<td>{(n.get('footprint') or {}).get('width', '')}×{(n.get('footprint') or {}).get('height', '')}, "
        f"{(n.get('footprint') or {}).get('bytes', '')} B</td>"
        f"<td><code>{e(str((n.get('footprint') or {}).get('sha256', ''))[:16])}…</code></td>"
        f"<td><code>{e(str((n.get('footprint') or {}).get('phash', '')))}</code></td></tr>"
        for n in report["items"]
    )
    summary = report.get("summary") or {}
    case = report.get("case", {})
    cal = report.get("calibration") or {}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font: 15px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; color: #111; margin: 0; padding: 32px; max-width: 980px; }}
  h1 {{ margin: 0 0 4px; font-size: 26px; }} h2 {{ font-size: 18px; margin: 28px 0 10px; }}
  .meta {{ color: #555; font-size: 13px; }} .tiles {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
  .tile {{ border: 1px solid #ddd; border-radius: 10px; padding: 10px 14px; min-width: 150px; }}
  .tile b {{ display: block; font-size: 22px; }} .tile span {{ color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
  .node {{ display: flex; gap: 14px; padding: 12px 0; border-top: 1px solid #eee; page-break-inside: avoid; }}
  .node img {{ width: 96px; height: 96px; object-fit: cover; border-radius: 8px; flex: 0 0 auto; }}
  .node code {{ color: #777; font-size: 12px; }} .reading {{ margin: 6px 0; }}
  .node ul {{ margin: 6px 0; padding-left: 18px; color: #333; }} .node table {{ font-size: 12px; border-collapse: collapse; margin-top: 6px; }}
  .node th {{ text-align: left; color: #666; font-weight: 500; padding: 1px 10px 1px 0; }} .node td {{ padding: 1px 0; }}
  .inventory {{ font-size: 12px; border-collapse: collapse; }} .inventory th, .inventory td {{ text-align: left; padding: 3px 10px 3px 0; border-bottom: 1px solid #eee; }}
  .plate {{ margin: 8px 0 0; }} .plate img {{ width: 100%; max-width: 860px; border-radius: 6px; }} .plate figcaption {{ color: #666; font-size: 11px; }}
  footer {{ margin-top: 28px; color: #666; font-size: 12px; border-top: 1px solid #ddd; padding-top: 12px; }}
  @media print {{ body {{ padding: 0; }} }}
</style></head><body>
<h1>{e(title)}</h1>
<p class="meta">Case: <strong>{e(str(case.get("name", case.get("id", "demo"))))}</strong>{(" · analyst " + e(str(case.get("analyst")))) if case.get("analyst") else ""} · generated {e(str(report.get("generated_at", "")))} · Lineage {e(str((report.get("tool") or {}).get("version", "")))}</p>
<div class="tiles">
  <div class="tile"><span>images</span><b>{summary.get("images", len(nodes))}</b></div>
  <div class="tile"><span>families</span><b>{summary.get("families", len(children.get(None, [])))}</b></div>
  <div class="tile"><span>mean empirical precision</span><b>{_pct(summary.get("mean_precision"))}</b></div>
  <div class="tile"><span>low-confidence decisions</span><b>{summary.get("low_confidence", "—")}</b></div>
</div>
<h2>How to read this</h2>
<p>Each image is placed under the image it was most cheaply derived from, using pixel measurements only (no metadata,
no file names). "Candidate original" means no other image in the case explains it more cheaply than calling it an
original; an earlier version outside this case may still exist. Precision figures come from an evaluation on synthetic edit chains with known truth: decisions with a
similar cost margin were correct that often. Treat low-margin decisions as leads to verify, not conclusions.</p>
<h2>Families</h2>
{tree_html}
<h2>Evidence inventory</h2>
<table class="inventory"><tr><th>id</th><th>file</th><th>size</th><th>SHA-256</th><th>pHash</th></tr>{inventory}</table>
<h2>Method and limitations</h2>
<p>{e(str(report.get("method", "")))}. The tree is reconstructed from the images in this case only: an earlier version
that was not supplied cannot appear, so "candidate original" means earliest within this corpus. Near-lossless edits
(small crops, mild filters) can tie between an image, its source and its source's source; the margin and the precision
figure say how clear each decision was. Metadata hints are unverified and easily stripped; they are not evidence.</p>
<footer>Method: {e(str(report.get("method", "")))}. Calibration runs: {e(", ".join(cal.get("runs", []) or []))}
({e(str(cal.get("generated_at", "")))}). Metadata hints, when shown, are unverified and easily stripped; they are not evidence.</footer>
</body></html>"""
