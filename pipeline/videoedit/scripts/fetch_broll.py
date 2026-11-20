"""Download B-roll photos from Wikimedia Commons (free licences only) and make a review sheet.

Usage: python fetch_broll.py <queries.json> <out_dir>
queries.json: {"states": "Vidhana Soudha Bengaluru", "army": "Indian Army Republic Day parade", ...}
Writes <out_dir>/<key>.jpg (1400 px wide), <out_dir>/credits.json and <out_dir>/sheet.jpg (all photos with
their key, to check that every photo really matches its topic). Keys already downloaded are skipped.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "videoedit-skill/0.1 (local video edit)"}
API = "https://commons.wikimedia.org/w/api.php?"
FREE = ("cc by", "cc-by", "cc0", "public domain", "pd", "godl", "fal", "attribution")


def get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                body = r.read()
            time.sleep(1.5)
            return body
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"rate limited: {url}")


queries = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
cpath = f"{out}/credits.json"
credits = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
for key, q in queries.items():
    if key in credits and os.path.exists(f"{out}/{key}.jpg"):
        continue
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
              "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 10, "prop": "imageinfo",
              "iiprop": "url|size|extmetadata", "iiurlwidth": 1400}
    pages = json.loads(get(API + urllib.parse.urlencode(params))).get("query", {}).get("pages", {})
    best = None
    for pg in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        ii = pg["imageinfo"][0]
        lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "").lower()
        if ii.get("width", 0) >= 1000 and ii.get("mime", "image/jpeg") != "image/svg+xml" and lic.startswith(FREE):
            best = (pg, ii)
            break
    if not best:
        print(f"{key}: NO RESULT for {q!r} -> use a card instead, or a different query")
        continue
    pg, ii = best
    raw = f"{out}/{key}.src"
    with open(raw, "wb") as f:
        f.write(get(ii["thumburl"]))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf", "scale=1400:-2", "-q:v", "3", f"{out}/{key}.jpg"],
                   check=True)
    os.remove(raw)
    meta = ii.get("extmetadata", {})
    clean = lambda v: re.sub("<[^>]+>", "", meta.get(v, {}).get("value", "")).strip()
    credits[key] = {"title": pg["title"], "author": clean("Artist"), "licence": clean("LicenseShortName"),
                    "page": ii.get("descriptionurl"), "query": q}
    print(f"{key}: {pg['title']} [{credits[key]['licence']}]")
    json.dump(credits, open(cpath, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

keys = [k for k in queries if os.path.exists(f"{out}/{k}.jpg")]
if keys:
    args, filt = [], []
    for i, k in enumerate(keys):
        args += ["-i", f"{out}/{k}.jpg"]
        filt.append(f"[{i}:v]scale=360:240:force_original_aspect_ratio=increase,crop=360:240,"
                    f"drawtext=text='{k}':x=8:y=8:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6[v{i}]")
    cols = min(4, len(keys))
    layout = "|".join(f"{(i % cols) * 360}_{(i // cols) * 240}" for i in range(len(keys)))
    graph = ";".join(filt) + ";" + "".join(f"[v{i}]" for i in range(len(keys)))
    graph += f"xstack=inputs={len(keys)}:layout={layout}:fill=black" if len(keys) > 1 else "null"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", graph, "-frames:v", "1", f"{out}/sheet.jpg"])
    print(f"review sheet: {out}/sheet.jpg")
json.dump(credits, open(cpath, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
