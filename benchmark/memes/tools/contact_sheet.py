"""Render labelled contact sheets from the resolved manifest for visual QA.

Usage: python contact_sheet.py originals <out.png>          one tile per family root (+components)
       python contact_sheet.py family <family-id> <out.png>  root + all variants of one family
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMAGES = ROOT / "images"
TILE = 170
FONT = ImageFont.load_default()


def tile(path, label):
    im = Image.new("RGB", (TILE, TILE + 30), "white")
    try:
        src = Image.open(path).convert("RGB")
        src.thumbnail((TILE, TILE))
        im.paste(src, ((TILE - src.width) // 2, (TILE - src.height) // 2))
    except Exception as e:  # noqa: BLE001
        ImageDraw.Draw(im).text((5, TILE // 2), f"ERR {e}"[:40], fill="red", font=FONT)
    ImageDraw.Draw(im).text((3, TILE + 3), label[:46], fill="black", font=FONT)
    ImageDraw.Draw(im).text((3, TILE + 15), label[46:92], fill="black", font=FONT)
    return im


def sheet(items, cols, out):
    rows = (len(items) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * (TILE + 6), rows * (TILE + 36)), "#dddddd")
    for i, (p, label) in enumerate(items):
        canvas.paste(tile(p, label), ((i % cols) * (TILE + 6), (i // cols) * (TILE + 36)))
    canvas.save(out)
    print("wrote", out, canvas.size)


def main():
    res = json.loads((ROOT / "manifest.resolved.json").read_text(encoding="utf-8"))
    fams = {f["id"]: f for f in res["families"]}
    if sys.argv[1] == "originals":
        items = []
        for f in res["families"]:
            o = f["original"]
            items.append((IMAGES / o["file"], f"{f['id']} | {o.get('width')}x{o.get('height')} {'TRUE' if o['is_true_source_photo'] else 'tmpl'}"))
            for c in f.get("components", []):
                items.append((IMAGES / c["file"], f"{f['id']} COMPONENT"))
        sheet(items, 6, sys.argv[2])
    else:
        f = fams[sys.argv[2]]
        items = [(IMAGES / f["original"]["file"], f"ROOT {f['original'].get('width')}x{f['original'].get('height')}")]
        for v in f["variants"]:
            items.append((IMAGES / v["file"], f"{v['file'].split('/')[-1]} | {v['origin']}"))
        for key in ("components", "related_not_derived"):
            for c in f.get(key, []):
                items.append((IMAGES / c["file"], f"{key.upper()} {c['file'].split('/')[-1]}"))
        sheet(items, 4, sys.argv[3])


if __name__ == "__main__":
    main()
