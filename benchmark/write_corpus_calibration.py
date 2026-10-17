"""Store a benchmark run's observed precision per margin bucket in calibration.json under
"corpora", so every confidence claim can show the number from a different corpus next to the
synthetic one. Usage: python benchmark/write_corpus_calibration.py results.json web-memes
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "backend" / "lineage" / "calibration.json"


def main(results_path: str, name: str) -> None:
    res = json.loads(Path(results_path).read_text(encoding="utf-8"))
    cal = json.loads(CAL.read_text(encoding="utf-8"))
    buckets = {}
    for b, v in res.get("calibration_check", {}).items():
        n = v.get("n", 0)
        if n:
            buckets[b] = {"correct": round(v["observed_precision"] * n), "n": n}
    cal.setdefault("corpora", {})[name] = {
        "buckets": buckets,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": f"benchmark/run_benchmark.py ({res.get('mode')}), {Path(results_path).name}",
        "note": "Observed precision of parent-child claims on this corpus, by the same margin buckets.",
    }
    CAL.write_text(json.dumps(cal, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for b, v in buckets.items():
        print(f"  {name} {b}: {v['correct']}/{v['n']} = {v['correct'] / v['n']:.0%}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
