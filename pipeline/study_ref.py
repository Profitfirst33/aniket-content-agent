#!/usr/bin/env python3
"""Study a reference reel: download it, transcribe what is actually SAID, and grab frames.

usage: study_ref.py <reel url> <job_dir>
Writes <job>/ref/ref.mp4, ref/transcript.txt (spoken words with times), ref/frames.jpg (contact sheet),
ref/info.json (duration, language). The caption alone is not enough: many creators write a description
there, not the script.
"""
import json, os, subprocess, sys

PY = "/opt/aniket-content-agent/venv/bin/python"
YTDLP = "/opt/aniket-content-agent/venv/bin/yt-dlp"
url, job = sys.argv[1], os.path.abspath(sys.argv[2])
ref = f"{job}/ref"
os.makedirs(ref, exist_ok=True)

subprocess.run([YTDLP, "-q", "--no-warnings", "-o", f"{ref}/ref.%(ext)s", "--remux-video", "mp4", url], check=True, timeout=300)
video = f"{ref}/ref.mp4"
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True).stdout.strip())

code = r"""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel("large-v3", device="cpu", compute_type="int8")
segs, info = m.transcribe(sys.argv[1], word_timestamps=False, vad_filter=True, beam_size=5)
out = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segs]
print(json.dumps({"language": info.language, "segments": out}, ensure_ascii=False))
"""
r = subprocess.run([PY, "-c", code, video], capture_output=True, text=True, timeout=1800)
data = json.loads(r.stdout.strip().splitlines()[-1])
with open(f"{ref}/transcript.txt", "w") as f:
    for s in data["segments"]:
        f.write(f"[{s['start']:5.1f}-{s['end']:5.1f}] {s['text']}\n")

step = max(1.0, dur / 12)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"fps=1/{step:.2f},scale=240:-1,tile=6x2",
                "-frames:v", "1", f"{ref}/frames.jpg"], check=True)
json.dump({"url": url, "duration": round(dur, 1), "language": data["language"], "frame_step": round(step, 2)},
          open(f"{ref}/info.json", "w"))
print(f"ref: {dur:.1f}s, {data['language']}, {len(data['segments'])} segments")
