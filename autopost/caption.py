#!/usr/bin/env python3
"""Write the Instagram caption for a finished reel.

usage: caption.py <job_dir> [--out <folder>]
Reads script.json + request.txt, asks Claude (prompts/caption.md), checks the rules,
writes caption.txt into <folder> (default: the job dir). Prints the caption.
"""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.path.expanduser("~/.local/bin/claude")


def problems(text, cta):
    bad = []
    if re.search(r"\blinks?\b", text, re.I):
        bad.append('uses the word "link"')
    if re.search("[—–]", text):
        bad.append("has an em or en dash")
    body = [l for l in text.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
    if not 3 <= len(body) <= 5:
        bad.append(f"{len(body)} lines, needs 3 to 5")
    if cta and not re.search(rf"\bComment {re.escape(cta)}\b", text):
        bad.append(f'no "Comment {cta}"')
    tags = re.findall(r"#\w+", text)
    if len(tags) > 5:
        bad.append(f"{len(tags)} hashtags, max 5")
    return bad


def main():
    job = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else job
    cta = json.load(open(f"{job}/script.json")).get("cta_word", "").upper()
    work = tempfile.mkdtemp(prefix="caption-")  # Claude works on copies, never inside the job dir
    for f in ("script.json", "request.txt"):
        if os.path.exists(f"{job}/{f}"):
            shutil.copy(f"{job}/{f}", work)
    prompt = open(f"{HERE}/prompts/caption.md").read()
    text, bad = "", ["not written"]
    for attempt in range(2):
        p = prompt if attempt == 0 else prompt + f"\n\nYour last caption broke these rules, rewrite it: {', '.join(bad)}"
        subprocess.run([CLAUDE, "-p", p, "--allowedTools", "Read,Write"], cwd=work, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=600)
        if os.path.exists(f"{work}/caption.txt"):
            text = open(f"{work}/caption.txt").read().strip()
            bad = problems(text, cta)
            if not bad:
                break
    os.makedirs(out, exist_ok=True)
    open(f"{out}/caption.txt", "w").write(text + "\n")
    shutil.rmtree(work, ignore_errors=True)
    if bad:
        print("WARN: " + "; ".join(bad), file=sys.stderr)
    print(text)
    sys.exit(0 if not bad else 2)


if __name__ == "__main__":
    main()
