"""Get the raw video into <job>/input/raw.mp4 from a Google Drive link, a YouTube/other URL, or a local file.

Usage: python fetch_input.py <link-or-path> <job_dir>
Prints duration, size and orientation so the right mode (short / long) can be picked.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

src, job = sys.argv[1], sys.argv[2]
os.makedirs(f"{job}/input", exist_ok=True)
dst = f"{job}/input/raw.mp4"

if os.path.exists(src):
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copy(src, dst)
elif "drive.google.com" in src or "docs.google.com" in src:
    m = re.search(r"/d/([\w-]+)", src) or re.search(r"id=([\w-]+)", src)
    if not m:
        sys.exit("could not find the Drive file id in the link")
    url = f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
        if "text/html" in r.headers.get("Content-Type", ""):
            sys.exit("Drive returned a web page, not the video: the file must be shared as 'Anyone with the link'")
        with open(dst, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
else:
    subprocess.run(["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "--no-write-subs",
                    "-o", dst, src], check=True)

info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=width,height,"
                                  "codec_type:stream_side_data=rotation", "-of", "json", dst],
                                 capture_output=True, text=True).stdout)
v = next(s for s in info["streams"] if s.get("codec_type") == "video")
w, h = v["width"], v["height"]
rot = abs(int(next((d.get("rotation", 0) for d in v.get("side_data_list", [])), 0) or 0))
if rot in (90, 270):
    w, h = h, w
dur = float(info["format"]["duration"])
mode = "short" if dur <= 75 else "long"
print(json.dumps({"file": dst, "duration": round(dur, 1), "width": w, "height": h,
                  "orientation": "vertical" if h > w else "horizontal", "mode": mode,
                  "size_mb": round(int(info["format"]["size"]) / 1e6)}))
