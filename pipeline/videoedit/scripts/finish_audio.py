"""Put a music bed under a rendered edit (ducked under the voice) and normalise to YouTube loudness.

Usage: python finish_audio.py <rendered.mp4> <out.mp4> [music.wav] [music_db]
Video is stream-copied; only the audio is rebuilt. Without music it only normalises.
"""
import json
import re
import subprocess
import sys

src, out = sys.argv[1], sys.argv[2]
music = sys.argv[3] if len(sys.argv) > 3 else None
music_db = float(sys.argv[4]) if len(sys.argv) > 4 else -13.0
TARGET = "I=-14:TP=-1.5:LRA=11"

if music:
    # the voice track drives a compressor on the music: music dips ~9 dB while someone talks
    graph = (f"[1:a]volume={music_db}dB,aformat=channel_layouts=stereo:sample_rates=48000[m];"
             "[0:a]aformat=channel_layouts=stereo:sample_rates=48000,asplit=2[v][key];"
             "[m][key]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350[duck];"
             "[v][duck]amix=inputs=2:duration=first:normalize=0[mix]")
    inputs = ["-i", src, "-i", music]
else:
    graph = "[0:a]aformat=channel_layouts=stereo:sample_rates=48000[mix]"
    inputs = ["-i", src]

measure = subprocess.run(["ffmpeg", "-hide_banner", *inputs, "-filter_complex",
                          graph + f";[mix]loudnorm={TARGET}:print_format=json[o]", "-map", "[o]", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure).group(0))
norm = (f"loudnorm={TARGET}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex",
                graph + f";[mix]{norm},aresample=48000[o]", "-map", "0:v", "-map", "[o]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
print(f"{out}: measured {m['input_i']} LUFS -> -14 target")
