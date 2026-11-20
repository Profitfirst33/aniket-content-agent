#!/usr/bin/env python3
"""Content agent pipeline: request -> script -> Flow avatar clips -> nick-style edit -> final reel.

usage: run_reel.py <job_dir> [--from STAGE]
The job dir needs request.txt (a topic, idea or reel link). Each stage skips itself when its
output already exists, so a failed run can be re-run and continues where it stopped.
Stages: study (reference reel), script, flow, prep, plan, render
The plan stage captures the real pages, lets Claude pick one of 4 templates from the screenshots and writes
deck.json (deck_reel.py draws it). If that fails, the older builder (spec.json -> build_reel.py) makes the reel.
"""
import fcntl, glob, json, os, re, shutil, subprocess, sys, time

P = "/opt/aniket-content-agent/pipeline"
VE = f"{P}/videoedit/scripts"
PY = "/opt/aniket-content-agent/venv/bin/python"
DOWNLOADS = "/var/lib/aniket-content-agent/Downloads"
FLOW_CWD = "/var/lib/aniket-content-agent/work"
OUTBOX = "/var/lib/aniket-content-agent/outbox"
SFX_DIR = "/usr/lib/node_modules/hyperframes/dist/skills/media-use/audio/assets/sfx"
SETTINGS = json.load(open(f"{P}/flow-settings.json"))
CLAUDE = os.path.expanduser("~/.local/bin/claude")

JOB = os.path.abspath(sys.argv[1])
EJ = f"{JOB}/edit"
STAGES = ["study", "script", "flow", "prep", "plan", "render"]
START = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else None


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(f"{JOB}/log.txt", "a") as f:
        f.write(line + "\n")


def sh(cmd, cwd=None, timeout=3600):
    r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"failed: {cmd}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def claude(prompt, tools, cwd, timeout=1800):
    r = subprocess.run([CLAUDE, "-p", prompt, "--allowedTools", tools], cwd=cwd, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "").strip()
    log(f"claude: {out[-600:]}")
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-800:]}")
    return out


def dur(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def should_run(stage, done_marker):
    if START and STAGES.index(stage) >= STAGES.index(START):
        return True
    markers = done_marker if isinstance(done_marker, tuple) else (done_marker,)
    return not any(os.path.exists(m) for m in markers)


def try_lock(f):
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


class NoCredits(Exception):
    """Flow balance too low for this reel; run_reel exits with code 3 so the bot pauses its queue."""


# ------------------------------------------------------------------ stages
def ref_url():
    m = re.search(r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels)/[A-Za-z0-9_-]+", open(f"{JOB}/request.txt").read())
    return m.group(0) if m else None


def stage_study():
    """Reference reel: download it, transcribe what is actually said, grab frames (ref/)."""
    url = ref_url()
    if not url:
        os.makedirs(f"{JOB}/ref", exist_ok=True)
        open(f"{JOB}/ref/none", "w").close()
        log("study: no reference reel")
        return
    out = sh(["python3", f"{P}/study_ref.py", url, JOB], timeout=2400)
    log(out.strip())


def stage_script():
    claude(open(f"{P}/prompts/script.md").read(), "WebSearch,WebFetch,Read,Write", JOB, 900)
    s = json.load(open(f"{JOB}/script.json"))
    assert 4 <= len(s["clips"]) <= 6, "script needs 4-6 clips"
    log(f"script: {s['title']} ({lang()})")


def lang():
    """"english" or "hinglish", chosen by the script writer from the reference reel's language."""
    return "english" if json.load(open(f"{JOB}/script.json")).get("language", "").lower().startswith("en") else "hinglish"


def stage_flow():
    s = json.load(open(f"{JOB}/script.json"))
    speaks = "in English (Indian accent)" if lang() == "english" else "in Hinglish (Hindi words, Indian accent)"
    clips = "\n".join(f"- Clip {i + 1} line: {c}" for i, c in enumerate(s["clips"]))
    prompt = (open(f"{P}/prompts/flow.md").read().replace("{N}", str(len(s["clips"]))).replace("{CLIPS}", clips)
              .replace("{NEED}", str(len(s["clips"]) * 12 + 10)).replace("{SPEAKS}", speaks))
    # one Flow run at a time: two jobs clicking in the same browser mix up prompts and downloads
    lock = open("/tmp/content-agent-flow.lock", "w")
    log("flow: waiting for the browser" if not try_lock(lock) else "flow: browser free")
    fcntl.flock(lock, fcntl.LOCK_EX)
    marker = f"{JOB}/.flow_start"
    open(marker, "w").close()
    out = claude(prompt, "mcp__content-browser__*", FLOW_CWD, 3000)
    fcntl.flock(lock, fcntl.LOCK_UN)
    m = re.search(r"NO_CREDITS\W*(\d*)", out)
    if m:
        raise NoCredits(m.group(1))
    t0 = os.path.getmtime(marker)
    files = sorted((f for f in glob.glob(f"{DOWNLOADS}/*.mp4") if os.path.getmtime(f) > t0), key=os.path.getmtime)
    if len(files) != len(s["clips"]):
        raise RuntimeError(f"expected {len(s['clips'])} downloads, found {len(files)}: {files}")
    os.makedirs(f"{JOB}/clips", exist_ok=True)
    for i, f in enumerate(files):
        shutil.copy(f, f"{JOB}/clips/clip{i + 1:02d}.mp4")
    open(f"{JOB}/clips/.done", "w").close()
    log(f"flow: {len(files)} clips")


def fix_words():
    """Let Claude correct misheard caption words against the script; keep the old file if the result is unusable."""
    path = f"{JOB}/words.json"
    before = json.load(open(path))
    shutil.copy(path, f"{JOB}/words.raw.json")
    claude(open(f"{P}/prompts/words_fix.md").read(), "Read,Write,Edit", JOB, 600)
    after = json.load(open(path))
    if len(after) != len(before) or any(abs(a[1] - b[1]) > 0.001 for a, b in zip(after, before)):
        log("words fix changed timings or length; keeping the original words")
        shutil.copy(f"{JOB}/words.raw.json", path)


def stage_prep():
    clips = sorted(glob.glob(f"{JOB}/clips/clip*.mp4"))
    os.makedirs(f"{EJ}/work", exist_ok=True)
    os.makedirs(f"{EJ}/assets/sfx", exist_ok=True)
    inputs = sum((["-i", c] for c in clips), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
    sh(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k", f"{JOB}/merged.mp4"])
    sh(["python3", f"{VE}/fetch_input.py", f"{JOB}/merged.mp4", EJ])
    sh([PY, f"{VE}/transcribe.py", f"{EJ}/input/raw.mp4", f"{EJ}/work/transcript.json", "large-v3",
        "en" if lang() == "english" else "hi"], timeout=3600)
    sh(["python3", f"{VE}/find_retakes.py", f"{EJ}/work/transcript.json", f"{EJ}/work/keep.json"])
    sh(["python3", f"{VE}/cut.py", f"{EJ}/input/raw.mp4", f"{EJ}/work/transcript.json", f"{EJ}/work/keep.json", f"{EJ}/work"])

    rx = f"{EJ}/work/roman_extra.json"
    if not os.path.exists(rx):
        json.dump({}, open(rx, "w"))
    for attempt in range(4):
        out = sh(["python3", f"{VE}/captions.py", f"{EJ}/work/cut_words.json", f"{EJ}/work/captions.json", rx])
        if " 0 Devanagari" in out:
            break
        if attempt == 3:
            raise RuntimeError("captions still have Devanagari words: " + out)
        claude(open(f"{P}/prompts/roman.md").read(), "Read,Write,Edit", JOB, 600)

    c = json.load(open(f"{EJ}/work/captions.json"))
    chunks = c["chunks"] if isinstance(c, dict) else c
    words = [[w["t"], w["s"], w["e"]] for ch in chunks for w in ch["words"]]
    clean = [w for i, w in enumerate(words) if not (i and w[0] == words[i - 1][0] and w[0].endswith("."))]
    json.dump(clean, open(f"{JOB}/words.json", "w"), ensure_ascii=False)
    fix_words()

    cut = f"{EJ}/work/cut.mp4"
    d = round(dur(cut) - 0.05, 2)
    open(f"{EJ}/work/duration.txt", "w").write(str(d))
    A = f"{EJ}/assets"
    sh(["ffmpeg", "-v", "error", "-y", "-i", cut, "-c:v", "libx264", "-crf", "16", "-g", "30", "-pix_fmt", "yuv420p", "-an", f"{A}/face.mp4"])
    sh(["ffmpeg", "-v", "error", "-y", "-i", cut, "-vn", "-ac", "2", "-ar", "48000", f"{A}/voice.wav"])
    sh(["ffmpeg", "-v", "error", "-y", "-i", f"{A}/face.mp4", "-vf",
        "scale=270:480,boxblur=20:3,eq=brightness=-0.22:saturation=1.2,scale=1080:1920", "-c:v", "libx264", "-crf", "24", "-g", "30", f"{A}/dark_bg.mp4"])
    sh(["ffmpeg", "-v", "error", "-y", "-i", clips[0], "-t", "3.6", "-an", "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "18", "-g", "30", f"{A}/raw.mp4"])
    sh([PY, f"{VE}/make_music.py", f"{A}/music.wav", str(d), "92"])
    for f in glob.glob(f"{SFX_DIR}/*.mp3"):
        shutil.copy(f, f"{A}/sfx/")
    shutil.copy(f"{P}/hyperframes.json", f"{EJ}/hyperframes.json")
    try:
        sh(["node", f"{P}/shot.mjs", f"{A}/flow.png"], timeout=120)
    except Exception as e:
        log(f"flow screenshot failed, using last one: {e}")
        shutil.copy(f"{P}/flow-fallback.png", f"{A}/flow.png")
    log("prep: background removal (slow on CPU)")
    sh(["hyperframes", "remove-background", f"{A}/face.mp4", "-o", f"{A}/face_cutout.webm", "--quality", "best"], cwd=EJ, timeout=5400)
    log(f"prep: done, {d}s, {len(clean)} words")


TEMPLATE_NAMES = {"paper": "Paper", "clean": "Clean", "notebook": "Notebook", "lime": "Lime"}


def recent_templates():
    """Templates of the latest other reels, newest first, so the feed does not repeat one look."""
    out = []
    for f in sorted(glob.glob(f"{os.path.dirname(JOB)}/*/deck.json"), key=os.path.getmtime, reverse=True):
        if os.path.dirname(f) != JOB:
            try:
                out.append(json.load(open(f))["template"])
            except Exception:
                pass
    return out[:3]


def old_plan():
    claude(open(f"{P}/prompts/plan.md").read(), "Read,Write,Edit,Bash(python3 /opt/aniket-content-agent/pipeline/build_reel.py:*),Bash(node /opt/aniket-content-agent/pipeline/capture.mjs:*)", JOB, 1200)
    sh(["python3", f"{P}/build_reel.py", JOB])
    log("plan: old editor spec ok")


def drop_deck(why):
    log(f"deck failed, using the old editor: {str(why)[-500:]}")
    if os.path.exists(f"{JOB}/deck.json"):
        os.replace(f"{JOB}/deck.json", f"{JOB}/deck.failed.json")


def stage_plan():
    recent = ", ".join(recent_templates()) or "none yet"
    try:
        claude(open(f"{P}/prompts/plan_deck.md").read().replace("{RECENT}", recent),
               "Read,Write,Edit,WebSearch,Bash(node /opt/aniket-content-agent/pipeline/grab.mjs:*),Bash(python3 /opt/aniket-content-agent/pipeline/media.py:*),Bash(python3 /opt/aniket-content-agent/pipeline/deck_reel.py:*)",
               JOB, 2400)
        sh(["python3", f"{P}/deck_reel.py", JOB, "--check"])
        d = json.load(open(f"{JOB}/deck.json"))
        log(f"plan: template {d['template']} ({d.get('reason', '')})")
    except Exception as e:
        drop_deck(e)
        old_plan()
    open(f"{JOB}/.plan_done", "w").close()


def stage_render():
    s = json.load(open(f"{JOB}/script.json"))
    for f in glob.glob(f"{EJ}/compositions/*.html"):
        os.remove(f)
    built = False
    if os.path.exists(f"{JOB}/deck.json"):
        try:
            sh(["python3", f"{P}/deck_reel.py", JOB])
            built = True
        except Exception as e:
            drop_deck(e)
    if not built:
        if not os.path.exists(f"{JOB}/spec.json"):
            old_plan()
        for f in glob.glob(f"{EJ}/compositions/*.html"):
            os.remove(f)
        sh(["python3", f"{P}/build_reel.py", JOB])
    out = sh(["hyperframes", "check"], cwd=EJ, timeout=900)
    log("check: " + " | ".join(l.strip() for l in out.splitlines() if "error(s)" in l))
    d = float(open(f"{EJ}/work/duration.txt").read())
    times = ",".join(f"{t:.1f}" for t in [1.5] + [d * k / 6 for k in range(1, 6)])
    sh(["hyperframes", "snapshot", "-o", f"{JOB}/snap", "--at", times, "--no-end"], cwd=EJ, timeout=900)
    sh(["hyperframes", "render", "-o", f"{EJ}/work/render.mp4", "--workers", "1", "--crf", "18", "--quiet"], cwd=EJ, timeout=5400)
    os.makedirs(f"{JOB}/output", exist_ok=True)
    final = f"{JOB}/output/{s['slug']}.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", f"{EJ}/work/render.mp4", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", final])
    os.remove(f"{EJ}/work/render.mp4")
    os.makedirs(OUTBOX, exist_ok=True)
    shutil.copy(final, f"{OUTBOX}/{time.strftime('%Y-%m-%d')}_{s['slug']}.mp4")
    log(f"render: {final} ({dur(final):.1f}s)")


RUN = [("study", (f"{JOB}/ref/info.json", f"{JOB}/ref/none"), stage_study),
       ("script", f"{JOB}/script.json", stage_script),
       ("flow", f"{JOB}/clips/.done", stage_flow),
       ("prep", f"{EJ}/assets/face_cutout.webm", stage_prep),
       ("plan", (f"{JOB}/.plan_done", f"{JOB}/spec.json"), stage_plan),
       ("render", f"{JOB}/output/.done", stage_render)]

if __name__ == "__main__":
    os.makedirs(JOB, exist_ok=True)
    assert os.path.exists(f"{JOB}/request.txt"), "job needs request.txt"
    # held while this job runs, so the bot never starts a second run of the same job after a restart
    running = open(f"{JOB}/.running", "w")
    fcntl.flock(running, fcntl.LOCK_EX)
    for name, marker, fn in RUN:
        if should_run(name, marker):
            log(f"== {name}")
            try:
                fn()
            except NoCredits as e:
                log(f"NO_CREDITS {e}")
                print(f"NO_CREDITS {e}", file=sys.stderr)
                sys.exit(3)
        else:
            log(f"== {name}: already done")
    open(f"{JOB}/output/.done", "w").close()
    s = json.load(open(f"{JOB}/script.json"))
    final = f"{JOB}/output/{s['slug']}.mp4"
    caption = f"Naya reel ready: {s['title']}"
    if os.path.exists(f"{JOB}/deck.json"):
        d = json.load(open(f"{JOB}/deck.json"))
        caption += f"\nTemplate: {TEMPLATE_NAMES.get(d['template'], d['template'])} ({d.get('reason', '')})"
        if os.path.exists(f"{JOB}/layout.txt"):
            caption += "\nLayout: " + {"1": "Blur background", "2": "Plain background"}.get(open(f"{JOB}/layout.txt").read().strip(), "?")
    else:
        caption += "\nTemplate: old editor"
    if os.environ.get("NO_DELIVER"):  # a test render: keep the file, send nothing
        log(f"DONE (not sent): {final}")
        sys.exit(0)
    r = subprocess.run(["python3", f"{P}/deliver.py", final, caption], capture_output=True, text=True)
    log((r.stdout or r.stderr).strip())
    log("DONE")
