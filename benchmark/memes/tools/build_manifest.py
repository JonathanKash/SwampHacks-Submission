"""Build benchmark/memes/manifest.json from the harvested URL pool and the
hand-curated provenance in sources.json.

Usage: python build_manifest.py            (reads tools/harvested.json + tools/sources.json)

Variant priority per family (capped at MAX_VARIANTS):
  1. Imgflip blank template(s)           kind=crop  (or override)      -> template reupload / crop / recompress
  2. KYM entry icon, original + facebook  kind=lowres                    -> site-recompressed copies
  3. KYM origin-section images            kind=caption|screenshot (curated)
  4. Wikipedia fair-use copy              kind=lowres
  5. KYM gallery photos (top by views)    kind=caption, minus curated exclusions
  6. KYM 'newsfeed' rendition of 2 of the gallery photos  kind=lowres, parent=<that caption variant>
  7. Imgflip user memes                   kind=caption
  8. KYM icon 'medium' (200x200 crop)     kind=crop
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAX_VARIANTS = 15
N_KYM_PHOTOS = 5
N_IMGFLIP_MEMES = 5
N_NEWSFEED = 2


def clean_url(u):
    u = u.strip()
    u = re.sub(r"(&quot;|!|\"|')+$", "", u)
    return u


def ext_of(u):
    m = re.search(r"\.(jpe?g|png|webp|gif|jfif|pnj)(?:[?_]|$)", u.lower())
    if not m:
        return "jpg"
    e = m.group(1)
    return {"jpeg": "jpg", "jfif": "jpg", "pnj": "png"}.get(e, e)


def matches(item, needles):
    hay = (item.get("url", "") + " " + item.get("title", "") + " " + item.get("alt", "")).lower()
    return any(n.lower() in hay for n in needles)


def main():
    harvested = json.loads((HERE / "harvested.json").read_text(encoding="utf-8"))
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["families"]
    families = []
    for src in sources:
        fid = src["id"]
        h = harvested[fid]
        orig_url = clean_url(src["original"]["url"])
        used = {orig_url}
        variants = []

        def add(url, kind, note, origin, **extra):
            url = clean_url(url)
            if url in used or len(variants) >= MAX_VARIANTS:
                return None
            used.add(url)
            idx = len(variants) + 1
            v = {"file": f"{fid}/v{idx:02d}_{kind}.{ext_of(url)}", "url": url, "kind": kind, "note": note, "origin": origin}
            v.update(extra)
            variants.append(v)
            return v

        # 1. Imgflip templates
        tkind = src.get("template_kind", ["crop", None])
        tk_over = src.get("imgflip_template_kinds", {})
        for ig in h["imgflip"]:
            if not ig.get("template_ok") or not ig.get("template_url"):
                continue
            code = re.search(r"i\.imgflip\.com/(?:\d+/)?(\w+)\.", ig["template_url"])
            code = code.group(1) if code else None
            if code and code in tk_over:
                kind, note = tk_over[code]
            else:
                kind = tkind[0]
                note = tkind[1] or f"Imgflip blank template '{ig['slug']}' (user-uploaded template copy, resized/recompressed)"
            add(ig["template_url"], kind, note, f"imgflip template {ig['slug']}")

        # 2. KYM icon original + facebook
        kym = next((k for k in h["kym"] if k.get("ok")), None)
        if kym and kym.get("icon") and not src.get("skip_icon"):
            icon = kym["icon"]
            ik = src.get("icon_kind", ["lowres", "Know Your Meme entry icon (site-hosted copy of the canonical template)"])
            add(icon, ik[0], ik[1], "kym icon original")
            add(icon.replace("/icons/original/", "/icons/facebook/"), "lowres", "Know Your Meme entry icon, 'facebook' rendition (server-side re-encode of the icon)", "kym icon facebook", parent="kym icon original")

        # 3. KYM origin-section images (curated kinds)
        okinds = src.get("origin_kinds", {})
        comp_urls = {clean_url(c["url"]) for c in src.get("components", [])} | {clean_url(c["url"]) for c in src.get("related_not_derived", [])}
        if kym:
            for oi in kym.get("origin_images", []):
                u = clean_url(oi["url"])
                if u in comp_urls or re.search(r"\.gif(\?|$)", u.lower()) or matches({"url": u, "title": oi.get("title", ""), "alt": oi.get("alt", "")}, src.get("kym_exclude", [])):
                    continue
                key = next((k for k in okinds if k in u), None)
                if key:
                    kind, note = okinds[key]
                else:
                    kind, note = "caption", f"KYM origin-section image: {oi.get('title') or oi.get('alt') or 'early example'}"
                add(u, kind, note, "kym origin section")

        # 4. Wikipedia fair-use copy
        wf = src.get("wiki_files")
        for w in h.get("wikipedia", []):
            for f in (w or {}).get("files", []):
                if "/wikipedia/en/" not in f["url"]:
                    continue  # only the fair-use meme copies, not Commons portraits
                if wf and not any(x.lower() in f["file"].lower() for x in wf):
                    continue
                if (f.get("mime") or "").endswith("gif"):
                    continue
                add(f["url"].split("?")[0], "lowres", f"Wikipedia fair-use low-resolution copy ({f['file']}, {f['w']}x{f['h']})", "wikipedia")
                break

        # 5. KYM gallery photos
        photos_added = []
        if kym:
            excl = src.get("kym_exclude", [])
            for p in kym.get("photos", []):
                if len(photos_added) >= N_KYM_PHOTOS:
                    break
                if matches(p, excl) or clean_url(p["url"]) in comp_urls:
                    continue
                t = p.get("title") or p.get("alt") or "untitled"
                v = add(p["url"], "caption", f"KYM gallery (sorted by views): '{t[:80]}'", "kym photo")
                if v:
                    v["page"] = p.get("page")
                    photos_added.append((v, p))
        # 6. newsfeed renditions of the first two gallery photos (2nd-generation derivative)
        for v, p in photos_added[:N_NEWSFEED]:
            nf = clean_url(p["url"]).replace("/photos/images/original/", "/photos/images/newsfeed/")
            add(nf, "lowres", f"KYM 'newsfeed' rendition (server-side downscale) of {v['file'].split('/')[-1]}", "kym photo newsfeed", parent=v["file"])

        # 7. Imgflip user memes
        n = 0
        # at least N_IMGFLIP_MEMES; keep filling with Imgflip memes while the family is short of MAX_VARIANTS - 1
        # (one slot is kept for the KYM 'medium' icon crop when the family has an icon)
        budget = max(N_IMGFLIP_MEMES, MAX_VARIANTS - 1 - len(variants))
        for ig in h["imgflip"]:
            for m in ig.get("memes", []):
                if n >= budget:
                    break
                if matches(m, src.get("kym_exclude", [])):
                    continue
                v = add(m["url"], "caption", f"Imgflip user meme: '{m['title'][:80]}'", f"imgflip meme ({ig['slug']})")
                if v:
                    v["page"] = m["page"]
                    n += 1

        # 8. KYM icon medium (square crop)
        if kym and kym.get("icon") and not src.get("skip_icon"):
            add(kym["icon"].replace("/icons/original/", "/icons/medium/"), "crop", "Know Your Meme entry icon, 'medium' rendition (200x200 square crop)", "kym icon medium", parent="kym icon original")

        o = dict(src["original"])
        o["url"] = orig_url
        o["file"] = f"{fid}/original.{ext_of(orig_url)}"
        fam = {"id": fid, "name": src["name"], "original": o, "variants": variants}
        if src.get("components"):
            fam["components"] = [{"file": f"{fid}/component{i+1}.{ext_of(c['url'])}", "url": clean_url(c["url"]), "note": c["note"]} for i, c in enumerate(src["components"])]
        if src.get("related_not_derived"):
            fam["related_not_derived"] = [{"file": f"{fid}/related{i+1}.{ext_of(c['url'])}", "url": clean_url(c["url"]), "note": c["note"]} for i, c in enumerate(src["related_not_derived"])]
        if kym:
            fam["kym_url"] = kym.get("url")
        families.append(fam)
        print(f"{fid:32s} variants={len(variants):2d} kinds={ {k: sum(1 for v in variants if v['kind']==k) for k in sorted({v['kind'] for v in variants})} }")

    out = {"_schema": "lineage-meme-benchmark/1", "_license_note": "Images are third-party copyrighted works downloaded for local, non-redistributed benchmark/testing use only. Do not commit or redistribute the images directory.",
           "families": families}
    (ROOT / "manifest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("families:", len(families), "variants:", sum(len(f["variants"]) for f in families))


if __name__ == "__main__":
    main()
