"""SQLite persistence: the pool (with true parents) and the pair-cost cache.

The engine never reads true parents; they live here only so the accuracy
endpoint can compare predictions against them.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from lineage.types import CostResult

SCHEMA = """
create table if not exists items (
    id          text primary key,
    file        text not null,
    true_parent text,
    edit        text,
    params      text not null default '{}',
    source      text not null default 'upload',
    created_at  real not null
);
create table if not exists costs (
    src      text not null,
    dst      text not null,
    total    real not null,
    semantic integer not null,
    terms    text not null,
    features text not null,
    primary key (src, dst)
);
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---- items --------------------------------------------------------------
    def add_item(self, item_id: str, file: str, true_parent: str | None, edit: str | None,
                 params: dict, source: str = "upload") -> dict:
        row = {
            "id": item_id, "file": file, "true_parent": true_parent, "edit": edit,
            "params": json.dumps(params), "source": source, "created_at": time.time(),
        }
        self.conn.execute(
            "insert into items (id, file, true_parent, edit, params, source, created_at) "
            "values (:id, :file, :true_parent, :edit, :params, :source, :created_at)", row)
        self.conn.commit()
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> dict:
        row = self.conn.execute("select * from items where id = ?", (item_id,)).fetchone()
        return self._item(row)

    def list_items(self) -> list[dict]:
        rows = self.conn.execute("select * from items order by created_at, id").fetchall()
        return [self._item(r) for r in rows]

    def delete_item(self, item_id: str) -> dict | None:
        """Remove one item. Its children are re-linked to its true parent so the accuracy
        counter keeps a sensible ground truth; cached costs touching it are dropped."""
        row = self.conn.execute("select * from items where id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        item = self._item(row)
        self.conn.execute("update items set true_parent = ? where true_parent = ?", (item["true_parent"], item_id))
        self.conn.execute("delete from costs where src = ? or dst = ?", (item_id, item_id))
        self.conn.execute("delete from items where id = ?", (item_id,))
        self.conn.commit()
        return item

    def clear(self) -> None:
        self.conn.executescript("delete from items; delete from costs;")
        self.conn.commit()

    @staticmethod
    def _item(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["params"] = json.loads(item["params"] or "{}")
        return item

    # ---- cost cache -----------------------------------------------------------
    def load_costs(self) -> dict[tuple[str, str], CostResult]:
        out: dict[tuple[str, str], CostResult] = {}
        for r in self.conn.execute("select * from costs"):
            out[(r["src"], r["dst"])] = CostResult(
                total=r["total"], semantic=bool(r["semantic"]),
                terms=json.loads(r["terms"]), features=json.loads(r["features"]))
        return out

    def save_costs(self, results: dict[tuple[str, str], CostResult]) -> None:
        self.conn.executemany(
            "insert or replace into costs (src, dst, total, semantic, terms, features) values (?, ?, ?, ?, ?, ?)",
            [(s, d, r.total, int(r.semantic), json.dumps(r.terms), json.dumps(r.features))
             for (s, d), r in results.items()])
        self.conn.commit()
