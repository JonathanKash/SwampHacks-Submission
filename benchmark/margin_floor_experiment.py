"""Does raising the pairwise direction-margin floor cut wrong-parent claims without abstaining too much?
Runs the pairwise harness over the synthetic runs and the Gemini edits for several floors and prints
direction / wrong-parent / abstained per corpus. Usage: python benchmark/margin_floor_experiment.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lineage import compare as cmp  # noqa: E402
from lineage.plugins.image_fingerprint import load_image_data  # noqa: E402


def pairs() -> list[tuple[str, Path, Path]]:
    out = []
    for run in sorted((ROOT / "data" / "synthetic").glob("run*")):
        truth = json.loads((run / "truth.json").read_text(encoding="utf-8"))["items"]
        by = {i["id"]: i for i in truth}
        out += [(f"synthetic-{run.name}", run / by[i["parent"]]["file"], run / i["file"]) for i in truth if i["parent"]]
    nb = ROOT / "benchmark" / "nanobanana"
    m = json.loads((nb / "manifest.json").read_text(encoding="utf-8"))
    for fam in m["families"]:
        src = nb / "sources" / fam["source"]["file"]
        if not src.exists():
            src = ROOT / "data" / "seeds" / fam["source"]["file"]
        for e in fam["edits"]:
            if src.exists() and (nb / e["file"]).exists():
                out.append(("gemini", src, nb / e["file"]))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    data: dict[Path, object] = {}

    def ld(p: Path):
        if p not in data:
            data[p] = load_image_data(p.name, p, None)
        return data[p]

    ps = pairs()
    print(len(ps), "pairs")
    # cost results are cached inside image_cost by content, so later floors are cheap
    for floor in (0.02, 0.03, 0.05, 0.08):
        cmp.MIN_DIRECTION_MARGIN = floor
        tally: dict[str, Counter] = {}
        for corpus, a, b in ps:
            r = cmp.compare(ld(a), ld(b), calibration={"buckets": {}})
            c = tally.setdefault(corpus, Counter())
            c["n"] += 1
            if r["verdict"] == "parent-child":
                c["correct" if r["parent"] == "A" else "wrong"] += 1
            else:
                c["abstained"] += 1
        print(f"\nfloor {floor}")
        for corpus, c in tally.items():
            n = c["n"]
            print(f"  {corpus:16s} direction {c['correct']/n:.0%}  wrong {c['wrong']/n:.0%} ({c['wrong']})  abstained {c['abstained']/n:.0%}")


if __name__ == "__main__":
    main()
