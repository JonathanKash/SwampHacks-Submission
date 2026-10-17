"""Generate the real-photo -> Gemini-edit corpus through the Antigravity CLI (`agy`).

For every source photo and every edit instruction, ask Antigravity (which has Gemini image
editing) to write the edited image next to the source. Ground truth is recorded as we go:
parent = the source file, edit = the instruction id. The driver is idempotent (skips edits
that already exist) so it can be re-run after interruptions.

Usage: python benchmark/nanobanana/make_corpus.py [--sources benchmark/nanobanana/sources] [--limit N]
Outputs: benchmark/nanobanana/edits/<src>/<edit>.png and benchmark/nanobanana/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

EDITS: dict[str, str] = {
    "object_add": "Add one small, realistic object that fits the scene (for example a bird, a cup, a bicycle, a sign). Keep everything else pixel-identical.",
    "object_remove": "Remove one clearly visible object or person from the scene and fill the area realistically. Keep everything else pixel-identical.",
    "background_swap": "Replace the background behind the main subject with a different but plausible background. Keep the main subject identical in position and size.",
    "style_change": "Re-render the whole image as a watercolor painting. Keep the composition, framing and aspect ratio identical.",
    "subtle_retouch": "Make a subtle retouch only: slightly brighten the main subject and soften skin or surface texture a little. No other change.",
    "text_overlay": "Add a short bold meme-style caption in white text with a black outline across the bottom of the image. Keep everything else pixel-identical.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_edit(src: Path, dst: Path, instruction: str, timeout_s: int = 420) -> tuple[bool, str]:
    prompt = (
        f"Image editing task. Input image: {src}. Edit instruction: {instruction} "
        f"Produce the edited image with your image-generation/editing tool and save it EXACTLY as {dst} (PNG). "
        "Do not draw with code or PIL; use the image tool. Reply with one word: DONE or FAILED."
    )
    try:
        proc = subprocess.run(["agy", "--dangerously-skip-permissions", "-p", prompt], capture_output=True, text=True,
                              timeout=timeout_s, encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, "agy not found"
    return dst.exists() and dst.stat().st_size > 10_000, out[-300:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", type=Path, default=Path(__file__).parent / "sources")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "edits")
    ap.add_argument("--limit", type=int, default=0, help="max edits to attempt this run (0 = all)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    manifest_path = Path(__file__).parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"families": []}
    done = {(f["source"]["file"], e["edit"]) for f in manifest["families"] for e in f["edits"]}
    families = {f["source"]["file"]: f for f in manifest["families"]}
    attempted = 0
    for src in sorted(p for p in args.sources.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}):
        fam = families.setdefault(src.name, {"source": {"file": src.name, "sha256": sha256(src)}, "edits": []})
        for edit_id, instruction in EDITS.items():
            if (src.name, edit_id) in done:
                continue
            if args.limit and attempted >= args.limit:
                break
            attempted += 1
            dst = args.out / src.stem / f"{edit_id}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            ok, tail = run_edit(src.resolve(), dst.resolve(), instruction)
            print(f"{src.name} / {edit_id}: {'ok' if ok else 'FAILED'} ({time.time() - t0:.0f}s)")
            if ok:
                fam["edits"].append({"edit": edit_id, "file": str(dst.relative_to(Path(__file__).parent)).replace("\\", "/"),
                                     "parent": src.name, "sha256": sha256(dst), "instruction": instruction, "tool": "antigravity/gemini"})
            else:
                fam.setdefault("failed", []).append({"edit": edit_id, "note": tail})
            manifest["families"] = list(families.values())
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(f["edits"]) for f in manifest["families"])
    print(f"manifest: {len(manifest['families'])} sources, {total} edits -> {manifest_path}")


if __name__ == "__main__":
    main()
