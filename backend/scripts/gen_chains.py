"""Synthetic chain generator (Phase 0).

From each seed image, grow a family: several chains of 4-6 random edits from the
fixed menu (AI restyle excluded), some of them branching off an existing node.
Saves every version as PNG plus truth.json with the true parent of each item.

Usage: python backend/scripts/gen_chains.py [--seeds data/seeds] [--out data/synthetic]
                                            [--chains 3] [--seed 0] [--name run1]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lineage import config  # noqa: E402
from lineage.edits.image_edits import EDIT_TYPES, apply_edit  # noqa: E402


def grow_family(seed_path: Path, family: str, out: Path, rng: random.Random, chains: int) -> list[dict]:
    items: list[dict] = []
    root_id = f"{family}_root"
    root_img = Image.open(seed_path).convert("RGB")
    root_img.save(out / f"{root_id}.png")
    items.append({"id": root_id, "file": f"{root_id}.png", "parent": None, "edit": None,
                  "params": {}, "family": family, "depth": 0})
    counter = 0
    for chain in range(chains):
        # First chain starts at the root; later chains branch off a random node.
        parent = items[0] if chain == 0 else rng.choice(items)
        length = rng.randint(4, 6)
        img = Image.open(out / parent["file"]).convert("RGB")
        for _ in range(length):
            edit = rng.choice(EDIT_TYPES)
            img, params = apply_edit(img, edit, rng)
            counter += 1
            item_id = f"{family}_{counter:02d}"
            img.save(out / f"{item_id}.png")
            node = {"id": item_id, "file": f"{item_id}.png", "parent": parent["id"], "edit": edit,
                    "params": params, "family": family, "depth": parent["depth"] + 1}
            items.append(node)
            parent = node
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=Path, default=config.DATA_DIR / "seeds")
    parser.add_argument("--out", type=Path, default=config.DATA_DIR / "synthetic")
    parser.add_argument("--chains", type=int, default=3, help="chains per family")
    parser.add_argument("--families", type=int, default=0, help="0 = all seeds")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    seeds = sorted(p for p in args.seeds.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    if args.families:
        seeds = seeds[: args.families]
    if not seeds:
        sys.exit(f"no seed images in {args.seeds}; run fetch_seeds.py first")

    run = args.out / (args.name or time.strftime("run_%Y%m%d_%H%M%S"))
    run.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for idx, seed_path in enumerate(seeds):
        items += grow_family(seed_path, f"f{idx}", run, rng, args.chains)
    (run / "truth.json").write_text(json.dumps({"items": items, "seed": args.seed}, indent=2))
    by_edit = {e: sum(1 for i in items if i["edit"] == e) for e in EDIT_TYPES}
    print(f"{len(items)} items in {len(seeds)} families -> {run}")
    print("edits:", by_edit)


if __name__ == "__main__":
    main()
