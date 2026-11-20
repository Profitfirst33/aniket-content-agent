"""Cut pauses and retakes out of a talking-head video.

Usage: python cut.py <video> <transcript.json> <keep.json> <out_dir> [--dry]
--dry writes cut_words.json / cut_map.json only (no video), e.g. to plan scenes before there is disk space.

keep.json: {"keep": [[start_sec, end_sec], ...]}  -- the takes to keep (retakes removed).
Inside every kept span, gaps between words longer than MAX_GAP are removed too.

Writes:
  <out_dir>/cut.mp4         1080x1920, h264, keyframe every 1s (seek-safe for HyperFrames)
  <out_dir>/cut_words.json  every kept word with its new start/end on the cut timeline
  <out_dir>/cut_map.json    the pieces: source start/end -> output start
"""
import json
import subprocess
import sys

MAX_GAP = 0.30   # a silence longer than this between words is cut
PAD = 0.06       # breathing room kept before/after each word run

video, transcript_path, keep_path, out_dir = sys.argv[1:5]
DRY = "--dry" in sys.argv[5:]
words = [w for seg in json.load(open(transcript_path, encoding="utf-8"))["segments"] for w in seg["words"]]
keep = json.load(open(keep_path))["keep"]

pieces = []  # [src_start, src_end, [words]]
for ks, ke in keep:
    span = [w for w in words if w["s"] >= ks - 0.02 and w["e"] <= ke + 0.02]
    if not span:
        continue
    run = [span[0]]
    for w in span[1:]:
        if w["s"] - run[-1]["e"] > MAX_GAP:
            pieces.append(run)
            run = []
        run.append(w)
    pieces.append(run)

# Whisper stretches word ends over silence, so also carve out measured silences.
probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vn", "-af",
                        f"silencedetect=n=-35dB:d={MAX_GAP}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
silences, st = [], None
for line in probe.splitlines():
    if "silence_start:" in line:
        st = float(line.split("silence_start:")[1].split()[0])
    elif "silence_end:" in line and st is not None:
        silences.append((st + PAD, float(line.split("silence_end:")[1].split()[0]) - PAD))
        st = None

def carve(s, e):
    out = [[s, e]]
    for a, b in silences:
        nxt = []
        for x, y in out:
            if b <= x or a >= y:
                nxt.append([x, y])
            else:
                if a - x > 0.08:
                    nxt.append([x, a])
                if y - b > 0.08:
                    nxt.append([b, y])
        out = nxt
    return out

segments = []
for run in pieces:
    s = max(0.0, run[0]["s"] - PAD)
    e = run[-1]["e"] + PAD
    for x, y in carve(s, e):
        inside = [w for w in run if w["s"] < y and w["e"] > x]
        if segments and x <= segments[-1][1]:
            segments[-1][1] = max(segments[-1][1], y)
            segments[-1][2].extend(w for w in inside if w not in segments[-1][2])
        else:
            segments.append([x, y, inside])

out_words, cut_map, t = [], [], 0.0
for s, e, run in segments:
    cut_map.append({"src_start": round(s, 3), "src_end": round(e, 3), "out_start": round(t, 3)})
    for w in run:
        ws, we = max(w["s"], s), min(w["e"], e)
        out_words.append({"text": w["w"], "start": round(t + ws - s, 3), "end": round(t + we - s, 3)})
    t += e - s

filt, labels = [], []
for i, (s, e, _) in enumerate(segments):
    filt.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];"
                f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d=0.015,afade=t=out:st={max(0, e - s - 0.015):.3f}:d=0.015[a{i}]")
    labels.append(f"[v{i}][a{i}]")
graph = ";".join(filt) + ";" + "".join(labels) + f"concat=n={len(segments)}:v=1:a=1[vc][a];" \
        "[vc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30[v]"

with open(f"{out_dir}/cut_graph.txt", "w") as f:
    f.write(graph)
if not DRY:
    subprocess.run([
      "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video,
      "-filter_complex_script", f"{out_dir}/cut_graph.txt", "-map", "[v]", "-map", "[a]",
      "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", "30", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-b:a", "192k", "-ar", "48000", f"{out_dir}/cut.mp4",
    ], check=True)

json.dump(out_words, open(f"{out_dir}/cut_words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(cut_map, open(f"{out_dir}/cut_map.json", "w"), indent=1)
print(f"pieces={len(segments)} duration={t:.2f}s words={len(out_words)}")
