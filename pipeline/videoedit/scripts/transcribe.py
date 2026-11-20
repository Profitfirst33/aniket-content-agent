"""Transcribe a talking-head video (Hindi/Hinglish) with word timestamps.

Usage: python transcribe.py <video> <out.json> [model] [language]

Whisper's VAD sometimes throws away real speech (one test video lost 30 s). After the VAD pass every
gap longer than 4 s that still has sound in it is transcribed again without VAD and merged in.
Output: {"segments": [{"start","end","text","words":[{"w","s","e","p"}]}]}
"""
import json
import os
import subprocess
import sys
import tempfile

from faster_whisper import WhisperModel

video, out = sys.argv[1], sys.argv[2]
model_name = sys.argv[3] if len(sys.argv) > 3 else "large-v3"
lang = sys.argv[4] if len(sys.argv) > 4 else "hi"

tmp = tempfile.mkdtemp()
wav = f"{tmp}/a.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
model = WhisperModel(model_name, device="cpu", compute_type="int8")


def run(path, offset=0.0, vad=True):
    segs, info = model.transcribe(path, language=lang, word_timestamps=True, vad_filter=vad, beam_size=5)
    res = []
    for seg in segs:
        ws = [{"w": w.word.strip(), "s": round(w.start + offset, 3), "e": round(w.end + offset, 3),
               "p": round(w.probability, 3)} for w in seg.words]
        res.append({"start": round(seg.start + offset, 3), "end": round(seg.end + offset, 3),
                    "text": seg.text.strip(), "words": ws})
        print(f"[{seg.start + offset:7.2f} -> {seg.end + offset:7.2f}] {seg.text.strip()}", flush=True)
    return res, info.duration


segments, duration = run(wav)


def loud(a, b):
    """Mean volume of a span in dB (speech is usually > -40 dB)."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(a), "-t", str(b - a), "-i", wav, "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    for line in r.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split()[0])
    return -99.0


bounds = [0.0] + [x for s in segments for x in (s["start"], s["end"])] + [duration]
gaps = [(bounds[k], bounds[k + 1]) for k in range(0, len(bounds) - 1, 2) if bounds[k + 1] - bounds[k] > 4.0]
for a, b in gaps:
    if loud(a, b) < -40:
        continue
    print(f"-- re-transcribing {a:.1f}-{b:.1f}s without VAD", flush=True)
    clip = f"{tmp}/gap.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", wav, clip], check=True)
    extra, _ = run(clip, offset=a, vad=False)
    for s in extra:
        s["words"] = [w for w in s["words"] if a <= w["s"] and w["e"] <= b + 0.05 and w["p"] > 0.3]
        if s["words"]:
            segments.append(s)
segments.sort(key=lambda s: s["start"])

with open(out, "w", encoding="utf-8") as f:
    json.dump({"language": lang, "duration": duration, "segments": segments}, f, ensure_ascii=False, indent=1)
os.remove(wav)
print(f"wrote {out}: {sum(len(s['words']) for s in segments)} words")
