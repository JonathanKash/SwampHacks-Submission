"""Harvest candidate image URLs + provenance text for meme families.

Sources: Imgflip (template + top user memes), Know Your Meme (entry icon,
origin section, top photos by views), Wikipedia (files on the article).
Output: benchmark/memes/tools/harvested.json (intermediate, reviewed by hand
before building manifest.json).

Usage: python harvest.py families.json harvested.json [id1,id2,...]
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/json,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
S = requests.Session(); S.headers.update(UA)


def get(url, **kw):
    try:
        return S.get(url, timeout=20, **kw)
    except Exception as e:  # noqa: BLE001
        print("  ERR", url, e)
        return None


def strip(t):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))).strip()


IMGFLIP_ITEM = re.compile(
    r"<div class='base-unit clearfix'><h2 class='base-unit-title'><a href='/i/(\w+)'>(.*?)</a></h2>"
    r".*?<img class='base-img' src='//i\.imgflip\.com/(\w+)\.(jpg|png|gif)'", re.S)


def imgflip(slug, n=14):
    """slug is either a named template ("Distracted-Boyfriend") or "<id>/<Name>"."""
    out = {"slug": slug, "template_url": None, "template_ok": False, "title": None, "memes": []}
    if "/" in slug:
        r = get(f"https://imgflip.com/memetemplate/{slug}")
        if r is not None and r.status_code == 200:
            m = re.search(r"(?:https?:)?//i\.imgflip\.com/([\w/]+\.(?:jpg|png))", r.text)
            if m:
                out["template_url"] = f"https://i.imgflip.com/{m.group(1)}"
    else:
        out["template_url"] = f"https://imgflip.com/s/meme/{slug}.jpg"
    if out["template_url"]:
        r = get(out["template_url"])
        out["template_ok"] = bool(r is not None and r.status_code == 200 and r.headers.get("content-type", "").startswith("image"))
    seen = set()
    for params in (None, {"sort": "top-365d"}, {"page": 2}):
        r = get(f"https://imgflip.com/meme/{slug}", params=params)
        if r is None or r.status_code != 200:
            continue
        if out["title"] is None:
            out["title"] = strip("".join(re.findall(r"<title>(.*?)</title>", r.text)))
        for m in IMGFLIP_ITEM.finditer(r.text):
            code, title, code2, ext = m.groups()
            if ext == "gif" or code2 in seen:
                continue
            seen.add(code2)
            out["memes"].append({"url": f"https://i.imgflip.com/{code2}.{ext}", "page": f"https://imgflip.com/i/{code}", "title": strip(title)})
        if len(out["memes"]) >= n:
            break
        time.sleep(0.3)
    out["memes"] = out["memes"][:n]
    return out


def kym(slug, n=10):
    out = {"slug": slug}
    r = get(f"https://knowyourmeme.com/memes/{slug}")
    if r is None or r.status_code != 200:
        out["ok"] = False
        out["status"] = None if r is None else r.status_code
        return out
    out["ok"] = True
    out["url"] = r.url
    h = r.text
    out["title"] = strip("".join(re.findall(r"<title>(.*?)</title>", h)))
    icon = re.findall(r'https://i\.kym-cdn\.com/entries/icons/(?:original|facebook)/(\d{3}/\d{3}/\d{3}/[^"\'\s<>]+)', h)
    out["icon"] = f"https://i.kym-cdn.com/entries/icons/original/{icon[0]}" if icon else None
    info = {}
    for k in ("Year", "Origin", "Type", "Status"):
        m = re.search(r"<dt>\s*%s\s*</dt>\s*<dd[^>]*>(.*?)</dd>" % k, h, re.S)
        if m:
            info[k.lower()] = strip(m.group(1))
    out["info"] = info
    m = re.search(r'id="origin".*?(?=<h2|<section id="(?:spread|notable)|id="spread")', h, re.S)
    out["origin_text"] = None
    out["origin_images"] = []
    out["origin_links"] = []
    if m:
        sec = m.group(0)
        out["origin_text"] = strip(sec)[:2500]
        for im in re.finditer(r"<img[^>]*>", sec):
            tag = im.group(0)
            src = re.search(r'data-src="([^"]+)"', tag) or re.search(r'src="(https://i\.kym-cdn[^"]+)"', tag)
            if not src:
                continue
            u = src.group(1)
            if "kym-cdn.com/photos/images" not in u:
                continue
            title = re.search(r'title="([^"]*)"', tag)
            alt = re.search(r'alt="([^"]*)"', tag)
            out["origin_images"].append({"url": u.replace("/newsfeed/", "/original/"), "newsfeed_url": u,
                                         "title": html.unescape(title.group(1) if title else ""),
                                         "alt": html.unescape(alt.group(1) if alt else "")})
        refs = re.findall(r'<a[^>]+href="(https?://(?!knowyourmeme)[^"]+)"[^>]*>', sec)
        out["origin_links"] = list(dict.fromkeys(refs))[:12]
    r = get(f"https://knowyourmeme.com/memes/{slug}/photos?sort=views")
    photos = []
    if r is not None and r.status_code == 200:
        blocks = r.text.split('<a class="item"')[1:]
        for b in blocks:
            b = b.split("</a>")[0]
            u = re.search(r'https://i\.kym-cdn\.com/photos/images/(?:original|masonry|newsfeed|list|small|facebook)/(\d{3}/\d{3}/\d{3}/[^"\s<>]+)', b)
            if not u:
                continue
            tail = u.group(1)
            if re.search(r"\.(gif|mp4|webm)$", tail.lower()):
                continue
            alt = re.search(r'alt="([^"]*)"', b); title = re.search(r'data-title="([^"]*)"', b); page = re.search(r'href="([^"]+)"', b)
            photos.append({"url": f"https://i.kym-cdn.com/photos/images/original/{tail}", "masonry_url": f"https://i.kym-cdn.com/photos/images/masonry/{tail}",
                           "page": (page.group(1) if page else "").replace(":443", ""), "title": html.unescape(title.group(1) if title else ""),
                           "alt": html.unescape(alt.group(1) if alt else "")[:200]})
            if len(photos) >= n:
                break
    out["photos"] = photos
    return out


def wikipedia(title):
    out = {"title": title, "ok": False, "files": []}
    r = get("https://en.wikipedia.org/w/api.php", params={"action": "query", "prop": "images|info", "inprop": "url", "titles": title,
                                                          "imlimit": 50, "format": "json", "redirects": 1})
    if r is None or r.status_code != 200:
        return out
    pages = r.json().get("query", {}).get("pages", {})
    files = []
    for p in pages.values():
        out["url"] = p.get("fullurl")
        out["resolved_title"] = p.get("title")
        for im in p.get("images", []):
            t = im["title"]
            if re.search(r"\.(svg|ogg|webm|ogv)$", t, re.I):
                continue
            if re.search(r"(icon|logo|symbol|Wiki|Commons|Question_book|Ambox|Edit-|Padlock|Star_|Crystal|Nuvola|Gnome|Folder|Flag_of)", t, re.I):
                continue
            files.append(t)
    if not files:
        return out
    r = get("https://en.wikipedia.org/w/api.php", params={"action": "query", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                                                          "iiextmetadatafilter": "LicenseShortName|ImageDescription|Artist",
                                                          "titles": "|".join(files[:20]), "format": "json"})
    if r is not None and r.status_code == 200:
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii.get("url"):
                continue
            em = ii.get("extmetadata", {})
            out["files"].append({"file": p["title"], "url": ii["url"], "w": ii.get("width"), "h": ii.get("height"), "mime": ii.get("mime"),
                                 "license": em.get("LicenseShortName", {}).get("value"),
                                 "desc": strip(em.get("ImageDescription", {}).get("value", ""))[:300], "page": ii.get("descriptionurl")})
    out["ok"] = bool(out["files"])
    return out


def main(cfg_path, out_path, only=None):
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    prev = json.loads(Path(out_path).read_text(encoding="utf-8")) if Path(out_path).exists() else {}
    for fam in cfg:
        fid = fam["id"]
        if only and fid not in only:
            continue
        print("==", fid, flush=True)
        rec = {"id": fid, "name": fam["name"], "imgflip": [], "kym": [], "wikipedia": []}
        for s in fam.get("imgflip", []):
            rec["imgflip"].append(imgflip(s)); time.sleep(0.4)
        for s in fam.get("kym", []):
            rec["kym"].append(kym(s)); time.sleep(0.4)
        for s in fam.get("wikipedia", []):
            rec["wikipedia"].append(wikipedia(s)); time.sleep(0.2)
        prev[fid] = rec
        Path(out_path).write_text(json.dumps(prev, indent=1, ensure_ascii=False), encoding="utf-8")
        for ig in rec["imgflip"]:
            print(f"   imgflip {ig['slug']}: tmpl={ig['template_ok']} memes={len(ig['memes'])} title={ig['title']!r}")
        for kk in rec["kym"]:
            print(f"   kym {kk['slug']}: ok={kk.get('ok')} photos={len(kk.get('photos', []))} origin_imgs={len(kk.get('origin_images', []))} icon={bool(kk.get('icon'))} info={kk.get('info')}")
        for w in rec["wikipedia"]:
            print(f"   wiki {w['title']}: files={len(w['files'])} -> {[f['file'] for f in w['files']][:6]}")
        sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3].split(",") if len(sys.argv) > 3 else None)
