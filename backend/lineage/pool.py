"""The live pool: files on disk + SQLite + the engine + the current tree.

One object, one lock. The API layer (app.py) and the pre-seed script both talk
to this, so the demo pool and a scripted pool are built the same way.
"""

from __future__ import annotations

import io
import json
import random
import threading
import uuid
from pathlib import Path

from PIL import Image

from lineage import config
from lineage.core.engine import Engine
from lineage.edits import image_edits
from lineage.evidence import build_evidence, load_calibration
from lineage.store import Store
from lineage.types import CostResult

try:  # explain() is a separate plug-in; the pool still works without it
    from lineage.plugins import image_explain
except ImportError:  # pragma: no cover
    image_explain = None  # type: ignore[assignment]

THUMB_SIDE = 220


def _label(result: CostResult) -> tuple[str, str]:
    """(short edge label, full sentence) for a chosen edge."""
    if image_explain is not None:
        return image_explain.short_label(result), image_explain.explain(result)
    ops = result.features.get("ops", [])
    text = "AI restyle (matched by meaning)" if result.semantic else (", ".join(ops) or "near-identical copy")
    return text[:28], text


class Pool:
    def __init__(self, data_dir: Path = config.DATA_DIR, use_clip: bool = True) -> None:
        self.dir = data_dir
        self.images = data_dir / "pool"
        self.thumbs = data_dir / "thumbs"
        self.images.mkdir(parents=True, exist_ok=True)
        self.thumbs.mkdir(parents=True, exist_ok=True)
        self.store = Store(data_dir / "lineage.sqlite")
        self.engine = Engine(use_clip=use_clip)
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
                  params: dict | None = None, source: str = "upload") -> dict:
        """Store a new version, fingerprint it, and rebuild the tree."""
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
            item = self.store.add_item(item_id, file, true_parent, edit, params or {}, source)
            self.engine.add_item(item_id, self.images / file)
            self.newest_id = item_id
            self._rebuild()
        return self.public_item(item)

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
            self.engine = Engine(use_clip=self.engine.embedder is not None)
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
        nodes, edges = [], []
        correct = total = 0
        for item in items:
            pred = result.parent.get(item["id"])
            is_root = pred is None
            hit = pred == truth[item["id"]]
            if truth[item["id"]] is not None or not is_root:
                total += 1
                correct += int(hit)
            reverse = self.engine.results.get((item["id"], pred)) if pred else None
            evidence = build_evidence(item["id"], pred, incoming[item["id"]], reverse,
                                      self.engine.root_cost, self.calibration)
            nodes.append({**self.public_item(item), "predicted_parent": pred, "correct": hit,
                          "root": is_root, "evidence": evidence})
            if pred is not None:
                res = self.engine.results[(pred, item["id"])]
                short, full = _label(res)
                edges.append({"src": pred, "dst": item["id"], "label": short, "explain": full,
                              "cost": round(res.total, 4), "semantic": res.semantic, "correct": hit,
                              "evidence": evidence})
        self.version += 1
        self.tree = {
            "version": self.version,
            "nodes": nodes,
            "edges": edges,
            "accuracy": {"correct": correct, "total": total, "pct": round(100 * correct / total, 1) if total else None},
            "newest_id": self.newest_id,
            "calibration": {"runs": self.calibration.get("runs", []), "generated_at": self.calibration.get("generated_at")},
        }

    # ---- read ---------------------------------------------------------------------
    @staticmethod
    def public_item(item: dict) -> dict:
        return {
            "id": item["id"],
            "url": f"/images/{item['file']}",
            "thumb": f"/thumbs/{item['id']}.jpg",
            "edit": item["edit"],
            "params": item["params"],
            "source": item["source"],
            "created_at": item["created_at"],
        }

    def items(self) -> list[dict]:
        return [self.public_item(i) for i in self.store.list_items()]

    def random_item(self, rng: random.Random | None = None) -> dict | None:
        items = self.store.list_items()
        return self.public_item((rng or random).choice(items)) if items else None

    def export_truth(self) -> str:
        """Ground truth as JSON (never served to the engine; used by the eval)."""
        return json.dumps(self.store.list_items(), indent=2)
