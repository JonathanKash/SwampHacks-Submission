"""Pre-seed the live demo pool with known chains so the tree is never empty.

Usage: python backend/scripts/seed_pool.py [--seeds data/seeds] [--families 3] [--chains 2]
                                           [--seed 0] [--reset] [--data-dir data]
Builds the same kind of chains as gen_chains.py, but through the Pool, so every
item gets a real id, thumbnail, SQLite row and cached costs. Stop the server
first (or run with --data-dir on a fresh dir) so SQLite is not shared mid-write.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lineage import config  # noqa: E402
from lineage.edits.image_edits import EDIT_TYPES, apply_edit  # noqa: E402
from lineage.pool import Pool  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=Path, default=config.DATA_DIR / "seeds")
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    parser.add_argument("--families", type=int, default=3)
    parser.add_argument("--chains", type=int, default=2, help="chains per family")
    parser.add_argument("--length", type=int, default=3, help="max edits per chain")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reset", action="store_true", help="clear the pool first")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    seeds = sorted(p for p in args.seeds.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})[: args.families]
    if not seeds:
        sys.exit(f"no seed images in {args.seeds}; run fetch_seeds.py first")

    pool = Pool(args.data_dir)
    if args.reset:
        pool.reset()
    for seed_path in seeds:
        root = pool.add_image(Image.open(seed_path), None, None, {"seed": seed_path.name}, source="seed")
        family = [root]
        for chain in range(args.chains):
            parent = root if chain == 0 else rng.choice(family)
            img = Image.open(pool.images / f"{parent['id']}.png")
            for _ in range(rng.randint(2, args.length)):
                edit = rng.choice(EDIT_TYPES)
                img, params = apply_edit(img, edit, rng)
                parent = pool.add_image(img, parent["id"], edit, params, source="seed")
                family.append(parent)
        print(f"{seed_path.name}: family of {len(family)}")
    acc = pool.tree["accuracy"]
    print(f"pool: {len(pool.engine.items)} items, tree accuracy {acc['pct']}% ({acc['correct']}/{acc['total']})")


if __name__ == "__main__":
    main()
