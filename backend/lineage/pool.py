"""The live pool: files on disk + SQLite + the engine + the current tree.

One object, one lock. The API layer (app.py) and the pre-seed script both talk
to this, so the demo pool and a scripted pool are built the same way. In audit
mode (industry cases) there is no ground truth: `correct` is always True and the
confidence comes from the calibrated evidence instead.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import threading
import time
import uuid
from pathlib import Path

from PIL import ExifTags, Image

from lineage import config
from lineage.core.engine import Engine
from lineage.edits import image_edits
from lineage.evidence import build_evidence, load_calibration
from lineage.plugins.image_fingerprint import ClipEmbedder
from lineage.store import Store
from lineage.types import CostResult

THUMB_SIDE = 220
_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def c2pa_present(raw: bytes | None) -> bool:
    """Presence check for a C2PA/Content Credentials manifest in the uploaded bytes:
    a JUMBF box ("jumb") carrying a "c2pa" label, in a JPEG APP11 segment or a PNG caBX
    chunk. Presence only; signatures are not verified here."""
    if not raw:
        return False
    head = raw[: 4 * 1024 * 1024]
    return b"jumb" in head and b"c2pa" in head


def exif_hints(img: Image.Image) -> dict:
    """Metadata hints: useful context, but easy to strip or forge, so never evidence."""
    try:
        exif = img.getexif()
    except Exception:  # pragma: no cover - corrupt EXIF
        return {"has_exif": False}
    if not exif:
        return {"has_exif": False}
    hints: dict = {"has_exif": True}
    make, model = exif.get(_EXIF_TAGS["Make"]), exif.get(_EXIF_TAGS["Model"])
    if make or model:
        hints["camera"] = " ".join(str(x).strip() for x in (make, model) if x)
    if exif.get(_EXIF_TAGS["Software"]):
        hints["software"] = str(exif.get(_EXIF_TAGS["Software"])).strip()
    stamp = exif.get(_EXIF_TAGS["DateTime"])
    try:
        stamp = exif.get_ifd(0x8769).get(_EXIF_TAGS["DateTimeOriginal"], stamp)
    except Exception:
        pass
    if stamp:
        hints["datetime"] = str(stamp)
    return hints


class Pool:
    def __init__(self, data_dir: Path = config.DATA_DIR, use_clip: bool = config.USE_CLIP,
                 embedder: ClipEmbedder | None = None, url_prefix: str = "", mode: str = "demo") -> None:
        self.dir = data_dir
        self.images = data_dir / "pool"
        self.thumbs = data_dir / "thumbs"
        self.images.mkdir(parents=True, exist_ok=True)
        self.thumbs.mkdir(parents=True, exist_ok=True)
        self.url_prefix = url_prefix.rstrip("/")
        self.mode = mode
        self.store = Store(data_dir / "lineage.sqlite")
        self.engine = Engine(use_clip=use_clip, embedder=embedder)
        self.calibration = load_calibration()
        self.lock = threading.RLock()
        self.version = 0
        self.newest_id: str | None = None
        self.tree: dict = {"version": 0, "nodes": [], "edges": [], "accuracy": {"correct": 0, "total": 0, "pct": None}}
        self._load()

    # ---- startup --------------------------------------------------------------
    def _load(self) -> None:
        with self.lock:
            self.engine.results.update(self.store.load_costs())
            items = self.store.list_items()
            for item in items:
                self.engine.add_item(item["id"], self.images / item["file"])
            if items:
                self.newest_id = items[-1]["id"]
            self._rebuild()

    # ---- mutations --------------------------------------------------------------
    def add_image(self, img: Image.Image, true_parent: str | None, edit: str | None,
                  params: dict | None = None, source: str = "upload", rebuild: bool = True,
                  raw: bytes | None = None) -> dict:
        """Store a new version, fingerprint it, and (by default) rebuild the tree.
        `raw` is the uploaded file as received (for metadata/manifest hints)."""
        params = dict(params or {})
        params.setdefault("metadata", {**exif_hints(img), "c2pa_manifest": c2pa_present(raw)})
        # Tamper-evident footprint of what was received, before any resizing.
        raw = io.BytesIO()
        img.save(raw, format="PNG")
        params.setdefault("footprint", {"sha256": hashlib.sha256(raw.getvalue()).hexdigest(),
                                        "width": img.size[0], "height": img.size[1], "bytes": len(raw.getvalue())})
        img = img.convert("RGB")
        w, h = img.size
        scale = config.MAX_SIDE / max(w, h)
        if scale < 1:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        item_id = uuid.uuid4().hex[:8]
        file = f"{item_id}.png"
        img.save(self.images / file)
        thumb = img.copy()
        thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
        thumb.save(self.thumbs / f"{item_id}.jpg", quality=85)
        with self.lock:
            item = self.store.add_item(item_id, file, true_parent, edit, params, source)
            self.engine.add_item(item_id, self.images / file)
            self.newest_id = item_id
            if rebuild:
                self._rebuild()
        return self.public_item(item)

    def add_images(self, images: list[tuple[Image.Image, str] | tuple[Image.Image, str, bytes]]) -> list[dict]:
        """Batch upload (audit mode): add everything, then rebuild once."""
        added = [self.add_image(entry[0], None, None, {"filename": entry[1]}, source="audit", rebuild=False,
                                raw=entry[2] if len(entry) > 2 else None)
                 for entry in images]
        with self.lock:
            self._rebuild()
        return added

    def apply_edit(self, parent_id: str, edit_type: str, params: dict | None = None,
                   rng: random.Random | None = None) -> tuple[Image.Image, dict]:
        """Run one menu edit (not restyle) on a pool image. Returns (image, params used)."""
        parent = self.store.get_item(parent_id)
        img = Image.open(self.images / parent["file"]).convert("RGB")
        return image_edits.apply_edit(img, edit_type, rng or random.Random(), **(params or {}))

    def image_bytes(self, item_id: str) -> bytes:
        item = self.store.get_item(item_id)
        return (self.images / item["file"]).read_bytes()

    def reset(self) -> None:
        with self.lock:
            self.store.clear()
            for f in list(self.images.iterdir()) + list(self.thumbs.iterdir()):
                f.unlink()
            self.engine = Engine(use_clip=self.engine.embedder is not None, embedder=self.engine.embedder)
            self.newest_id = None
            self._rebuild()

    # ---- tree -------------------------------------------------------------------
    def _rebuild(self) -> None:
        """Recompute the tree (costs are cached per pair, so this is incremental)."""
        before = set(self.engine.results)
        result = self.engine.build_tree()
        new = {k: v for k, v in self.engine.results.items() if k not in before}
        if new:
            self.store.save_costs(new)
        items = self.store.list_items()
        truth = {i["id"]: i["true_parent"] for i in items}
        # Every measured cost into each node: the evidence a decision is made from.
        incoming: dict[str, dict[str, CostResult]] = {i["id"]: {} for i in items}
        for (src, dst), res in self.engine.results.items():
            if dst in incoming:
                incoming[dst][src] = res
        children: dict[str, list[str]] = {i["id"]: [] for i in items}
        for node, parent in result.parent.items():
            if parent is not None:
                children[parent].append(node)

        def descendants(node: str) -> set[str]:
            out, stack = set(), list(children[node])
            while stack:
                n = stack.pop()
                if n not in out:
                    out.add(n)
                    stack.extend(children[n])
            return out

        nodes, edges = [], []
        correct = total = 0
        precisions: list[float] = []
        low_confidence = 0
        for item in items:
            pred = result.parent.get(item["id"])
            is_root = pred is None
            # Audit mode has no ground truth: nothing is "wrong", confidence is in the evidence.
            hit = True if self.mode == "audit" else pred == truth[item["id"]]
            if self.mode != "audit" and (truth[item["id"]] is not None or not is_root):
                total += 1
                correct += int(hit)
            reverse = self.engine.results.get((item["id"], pred)) if pred else None
            evidence = build_evidence(item["id"], pred, incoming[item["id"]], reverse,
                                      self.engine.root_cost, self.calibration, descendants(item["id"]))
            precision = evidence["confidence"]["precision"]
            if not is_root and precision is not None:
                precisions.append(precision)
                low_confidence += int(precision < 0.8)
            nodes.append({**self.public_item(item), "predicted_parent": pred, "correct": hit,
                          "root": is_root, "evidence": evidence})
            if pred is not None:
                res = self.engine.results[(pred, item["id"])]
                short, full = self.engine.explain(res)
                edges.append({"src": pred, "dst": item["id"], "label": short, "explain": full,
                              "cost": round(res.total, 4), "semantic": res.semantic, "correct": hit,
                              "evidence": evidence})
        self.version += 1
        self.tree = {
            "version": self.version,
            "mode": self.mode,
            "nodes": nodes,
            "edges": edges,
            "accuracy": {"correct": correct, "total": total, "pct": round(100 * correct / total, 1) if total else None},
            "summary": {
                "images": len(items),
                "families": sum(1 for n in nodes if n["root"]),
                "mean_precision": round(sum(precisions) / len(precisions), 3) if precisions else None,
                "low_confidence": low_confidence,
            },
            "newest_id": self.newest_id,
            "calibration": {"runs": self.calibration.get("runs", []), "generated_at": self.calibration.get("generated_at")},
        }

    # ---- read ---------------------------------------------------------------------
    def public_item(self, item: dict) -> dict:
        params = dict(item["params"])
        metadata = params.pop("metadata", None)
        footprint = params.pop("footprint", None)
        if footprint is not None and item["id"] in self.engine.data:
            footprint = {**footprint, "phash": f"{self.engine.data[item['id']].phash:016x}"}
        return {
            "id": item["id"],
            "footprint": footprint,
            "url": f"{self.url_prefix}/images/{item['file']}",
            "thumb": f"{self.url_prefix}/thumbs/{item['id']}.jpg",
            "edit": item["edit"],
            "params": params,
            "source": item["source"],
            "created_at": item["created_at"],
            "metadata": metadata,
        }

    def items(self) -> list[dict]:
        return [self.public_item(i) for i in self.store.list_items()]

    def random_item(self, rng: random.Random | None = None) -> dict | None:
        items = self.store.list_items()
        return self.public_item((rng or random).choice(items)) if items else None

    def report(self, case: dict | None = None) -> dict:
        """Exportable provenance report: the tree plus every decision's evidence."""
        originals = [n for n in self.tree["nodes"] if n["root"]]
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "case": case or {"id": "demo"},
            "summary": self.tree.get("summary"),
            "originals": [n["id"] for n in originals],
            "decisions": [
                {
                    "image": e["dst"],
                    "parent": e["src"],
                    "edit": e["explain"],
                    "cost": e["cost"],
                    "semantic": e["semantic"],
                    "margin": e["evidence"]["margin"],
                    "empirical_precision": e["evidence"]["confidence"]["precision"],
                    "measurements": e["evidence"]["measurements"],
                    "reasons": e["evidence"]["reasons"],
                }
                for e in self.tree["edges"]
            ],
            "items": self.tree["nodes"],
            "method": "asymmetric information-loss cost over ORB/RANSAC-registered pairs; "
                      "minimum spanning arborescence (Chu-Liu/Edmonds); confidence calibrated on synthetic edit chains",
            "calibration": self.tree.get("calibration"),
        }

    def diff_plates(self) -> dict[str, bytes]:
        """PNG diff plate for every derived copy against its predicted source (report exhibits)."""
        from lineage.diff import diff_plate, encode_png

        plates: dict[str, bytes] = {}
        for node in self.tree["nodes"]:
            src = node.get("predicted_parent")
            if src and src in self.engine.data and node["id"] in self.engine.data:
                plate, _ = diff_plate(self.engine.data[src], self.engine.data[node["id"]])
                plates[node["id"]] = encode_png(plate)
        return plates

    def export_truth(self) -> str:
        """Ground truth as JSON (never served to the engine; used by the eval)."""
        return json.dumps(self.store.list_items(), indent=2)
