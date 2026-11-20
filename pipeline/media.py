#!/usr/bin/env python3
"""Fetch a real image for a deck `image` scene into edit/assets/img/<name>.jpg. Run from the job folder.

usage: media.py og <page_url> <name>      the page's own share image (og:image / twitter:image)
       media.py image <image_url> <name>  one image file, from the product's or article's own site
Prints the saved size; Read the jpg afterwards to check it really shows the topic.

B-roll (free Mixkit stock video, free licence for commercial use):
       media.py broll <word> [<word> ...]  search Mixkit, one single word per search (cyberpunk, robot, coding, brain, money ...);
                                           prints "<id> | <title>" lines
       media.py broll-get <id> <name>      save that clip as edit/assets/broll/<name>.mp4 (12 s, no sound) plus <name>.jpg,
                                           3 frames from it; Read the jpg to check it really shows what is being said
"""
import html, json, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/150.0 Safari/537.36"}
OG = re.compile(r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)(?::src)?["'][^>]*>""", re.I)
MIN_W = 500


def get(url):
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"not a web address: {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read(25_000_000)


def og_url(page):
    text = get(page).decode("utf-8", "ignore")
    m = OG.search(text)
    c = m and re.search(r"""content=["']([^"']+)""", m.group(0), re.I)
    if not c:
        raise SystemExit("this page has no share image")
    return urllib.parse.urljoin(page, html.unescape(c.group(1)))


def save(url, name):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise SystemExit("name: lowercase letters, digits and _ only")
    os.makedirs("edit/assets/img", exist_ok=True)
    dst = f"edit/assets/img/{name}.jpg"
    with tempfile.NamedTemporaryFile() as t:
        t.write(get(url))
        t.flush()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", t.name, "-frames:v", "1", "-vf", "scale='min(1600,iw)':-2", "-q:v", "3", dst], check=True)
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", dst],
                          capture_output=True, text=True, check=True).stdout.strip().split(",")[:2]
    if int(w) < MIN_W:
        os.remove(dst)
        raise SystemExit(f"too small ({w}x{h}), pick another image")
    print(f"saved {dst} {w}x{h} from {url}")


BROLL = "edit/assets/broll"


def broll_search(words):
    os.makedirs(BROLL, exist_ok=True)
    found = {}
    cache = f"{BROLL}/.search.json"
    if os.path.exists(cache):
        found = json.load(open(cache))
    for w in words:
        slug = re.sub(r"[^a-z0-9]+", "-", w.lower()).strip("-")
        try:
            text = get(f"https://mixkit.co/free-stock-video/{slug}/").decode("utf-8", "ignore")
        except Exception as e:
            print(f"== {w}: search failed ({e})")
            continue
        hits = []
        for m in re.finditer(r'<video src="(https://assets\.mixkit\.co/[^"]+-360\.mp4)".*?overlay-video-title">\s*([^<]+?)\s*</span>', text, re.S):
            url, title = m.groups()
            vid = re.search(r"/(\d+)-(?:video-)?360\.mp4$", url)
            if vid and vid.group(1) not in {h[0] for h in hits}:
                hits.append((vid.group(1), html.unescape(title), url))
        print(f"== {w}: {len(hits)} clips" + ("" if hits else " (try another single word)"))
        for vid, title, url in hits[:15]:
            found[vid] = {"title": title, "url": url}
            print(f"{vid} | {title}")
    json.dump(found, open(cache, "w"))


def broll_get(vid, name):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise SystemExit("name: lowercase letters, digits and _ only")
    cache = f"{BROLL}/.search.json"
    found = json.load(open(cache)) if os.path.exists(cache) else {}
    if vid not in found:
        raise SystemExit("unknown id: run media.py broll <word> first and copy an id it printed")
    src = found[vid]["url"]
    dst = f"{BROLL}/{name}.mp4"
    with tempfile.NamedTemporaryFile(suffix=".mp4") as t:
        for size in ("1080", "720", "360"):
            try:
                t.seek(0), t.truncate()
                t.write(get(src.replace("-360.mp4", f"-{size}.mp4")))
                t.flush()
                break
            except Exception:
                continue
        else:
            raise SystemExit("download failed, pick another clip")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", t.name, "-t", "12", "-an", "-vf", "scale=1280:-2,fps=30",
                        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-g", "30", "-pix_fmt", "yuv420p", dst], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", dst, "-vf", "fps=1/3.5,scale=420:-2,tile=3x1", "-frames:v", "1", f"{BROLL}/{name}.jpg"], check=True)
    print(f"saved {dst} ({found[vid]['title']}) and {BROLL}/{name}.jpg")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "broll":
        broll_search(sys.argv[2:])
        raise SystemExit(0)
    if len(sys.argv) == 4 and sys.argv[1] == "broll-get":
        broll_get(sys.argv[2], sys.argv[3])
        raise SystemExit(0)
    if len(sys.argv) != 4 or sys.argv[1] not in ("og", "image"):
        raise SystemExit(__doc__)
    save(og_url(sys.argv[2]) if sys.argv[1] == "og" else sys.argv[2], sys.argv[3])
