"""Build a HyperFrames edit project from a scene plan (premium B-roll style, 1080x1920).

Usage: python build_edit.py <plan.json> <project_dir>

plan.json (all times in seconds on the CUT timeline):
{
  "cut": "/abs/work/cut.mp4", "cut_map": "/abs/work/cut_map.json", "captions": "/abs/work/captions.json",
  "images": "/abs/work/images", "duration": 144.0, "captions_mode": "full" | "keywords" | "off",
  "scenes": [
    {"type": "card",    "start": 0.9, "end": 4.0, "top": "IS SAAL MERA TAX", "big": "₹9,43,959", "bottom": "kahan gaya?",
                        "roll_to": 943959, "color": "#fff", "glow": "#E0222E",
                        "chips": ["A 17%", "B 8%", "= 25%"], "bars": [{"label": "States", "pct": 22, "miss": false}]},
    {"type": "photo",   "start": 24.5, "end": 28.0, "img": "states.jpg", "pos": "50% 50%", "tag": "#1 · 22% · States",
                        "big": "₹2,07,671", "line": "Local development", "roll_to": 207671},
    {"type": "badge",   "start": 21.7, "end": 24.4, "n": 1, "pct": "22%"},
    {"type": "sticker", "start": 5.9, "end": 7.7, "text": "ITR validated ✅"},
    {"type": "progress","start": 21.7, "end": 105, "items": [{"at": 21.7, "label": "1/9 · States ko"}]},
    {"type": "quote",   "start": 125.5, "end": 129.4, "line1": "Jis tarike se kharch karenge,",
                        "line2": "waise hi returns banenge", "accent": ["returns"], "bubble": true},
    {"type": "cta",     "start": 135.6, "end": 140.6, "kicker": "Comment karke batao", "line": "Aapka tax kitna tha?"},
    {"type": "end",     "start": 141.4, "thumbs": ["thumb1.jpg", "thumb2.jpg"]}
  ]
}
Captions hide on full-screen scenes (card, quote, end) and move up into the photo during split-screen.
"""
import glob
import json
import os
import re
import shutil
import sys
from string import Template

plan = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]
DUR = float(plan["duration"])
CUTS = [c["out_start"] for c in json.load(open(plan["cut_map"]))][1:]
SFX_SRC = (glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/hyperframes/dist/skills/media-use/audio/assets/sfx"))
           or glob.glob("/usr/local/lib/node_modules/hyperframes/dist/skills/media-use/audio/assets/sfx")
           or glob.glob("/opt/homebrew/lib/node_modules/hyperframes/dist/skills/media-use/audio/assets/sfx"))
if not SFX_SRC:
    sys.exit("HyperFrames sound effects not found: run `npx hyperframes --version` once, then try again")
SFX_SRC = SFX_SRC[0]

SPLIT_H = 1000   # photo takes the top 1000 px, the face the rest
FACE_DY = 420    # face video slides down this much so the head sits under the photo
CAP_FACE, CAP_SPLIT = 1560, 862
RED, YELLOW = "#E0222E", "#FFD84D"
GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/>"
         "</filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.55'/></svg>\")")


def T(_tpl, **kw):
    return Template(_tpl).safe_substitute(**kw)


JS_INR = """function inr(n){n=Math.round(n);var s=String(n);if(s.length<=3)return s;
var t=s.slice(-3),h=s.slice(0,-3),p=[];while(h.length>2){p.unshift(h.slice(-2));h=h.slice(0,-2);}
if(h)p.unshift(h);return p.join(",")+","+t;}
function roll(sel,to,at,dur,pre,suf,from){var o={v:from||0};var el=document.querySelector(sel);
tl.fromTo(o,{v:from||0},{v:to,duration:dur||1.1,ease:"expo.out",immediateRender:!from,onUpdate:function(){el.textContent=(pre===undefined?"\\u20b9":pre)+inr(o.v)+(suf||"");}},at);}
function words(sel,at,gap){var ws=document.querySelectorAll(sel);for(var i=0;i<ws.length;i++){
tl.fromTo(ws[i],{opacity:0,filter:"blur(8px)"},{opacity:1,filter:"blur(0px)",duration:0.16,ease:"power4.out"},at+i*(gap||0.07));}}
"""


def split_words(text, cls, accent=()):
    return " ".join(f'<span class="{cls}{" acc" if w.strip(",.?") in accent else ""}">{w}</span>' for w in text.split(" "))


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- project plumbing
class Project:
    def __init__(self, out, bg="#000"):
        self.dir = out
        self.hosts, self.audio, self.root_js, self.extra = [], [], [], []
        self.bg, self.n_scene, self.n_sfx = bg, 0, 0
        os.makedirs(f"{out}/compositions", exist_ok=True)
        os.makedirs(f"{out}/assets/sfx", exist_ok=True)
        for f in glob.glob(f"{out}/compositions/*.html"):
            os.remove(f)
        # hard link, not a copy: the cut is hundreds of MB
        if os.path.exists(f"{out}/assets/cut.mp4"):
            os.remove(f"{out}/assets/cut.mp4")
        try:
            os.link(plan["cut"], f"{out}/assets/cut.mp4")
        except OSError:
            shutil.copy(plan["cut"], f"{out}/assets/cut.mp4")
        for f in glob.glob(f"{SFX_SRC}/*.mp3"):
            shutil.copy(f, f"{out}/assets/sfx/")
        for f in glob.glob(f"{plan['images']}/*"):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                shutil.copy(f, f"{out}/assets/")

    def scene(self, sid, start, end, css, body, js, z=5, transparent=False):
        self.n_scene += 1
        html = T("""<template>
<style>
#root{position:absolute;inset:0;overflow:hidden;background:$bg;font-family:Montserrat,Inter,sans-serif}
$css
</style>
<div id="root" data-composition-id="$sid" data-width="1080" data-height="1920">
$body
</div>
<script>
const tl = gsap.timeline({paused:true});
$inr
$js
window.__timelines["$sid"] = tl;
</script>
</template>
""", bg="transparent" if transparent else "none", sid=sid, css=css, body=body, js=js, inr=JS_INR)
        open(f"{self.dir}/compositions/{sid}.html", "w", encoding="utf-8").write(html)
        self.hosts.append(
            f'<div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
            f'data-start="{start:.2f}" data-duration="{end - start:.2f}" data-track-index="{1 + self.n_scene % 3}" '
            f'data-track-kind="graphics" data-width="1080" data-height="1920" style="z-index:{z}"></div>')

    def sfx(self, name, at, vol=0.45, dur=1.0):
        self.n_sfx += 1
        self.audio.append(
            f'<audio id="sfx{self.n_sfx}" class="clip" src="assets/sfx/{name}.mp3" data-start="{max(0, at):.2f}" '
            f'data-duration="{dur}" data-track-index="{10 + self.n_sfx % 8}" data-volume="{vol}"></audio>')

    def punch_ins(self, full_screen):
        """Alternate face framing on every face shot and on every cut inside one (hides jump cuts)."""
        def covered(t):
            return any(s - 0.05 <= t < e for s, e in full_screen)
        scale, last = 1.0, -9
        for t in sorted(set([0.0] + [e for _, e in full_screen] + CUTS)):
            if covered(t) or t - last < 1.4 or t >= DUR:
                continue
            scale = 1.16 if scale == 1.0 else 1.0
            self.root_js.append(f'tl.set("#cam",{{scale:{scale}}},{t:.2f});')
            last = t

    def write(self, extra_body=""):
        idx = T("""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:$bg}
#root{position:relative;width:1080px;height:1920px;overflow:hidden}
#camwrap{position:absolute;inset:0;overflow:hidden;z-index:1}
#cam{position:absolute;inset:0;transform-origin:50% 30%}
#face{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover}
$extra
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="$dur" data-width="1080" data-height="1920">
<div id="camwrap" data-layout-allow-overflow><div id="cam"><video id="face" class="clip" src="assets/cut.mp4" data-start="0" data-duration="$dur" data-track-index="0" data-has-audio="true" playsinline></video></div></div>
$extra_body
$hosts
$audio
</div>
<script>
const tl = gsap.timeline({ paused: true });
$js
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
""", bg=self.bg, dur=DUR, extra="\n".join(self.extra), extra_body=extra_body,
                hosts="\n".join(self.hosts), audio="\n".join(self.audio), js="\n".join(self.root_js))
        open(f"{self.dir}/index.html", "w", encoding="utf-8").write(idx)
        if not os.path.exists(f"{self.dir}/hyperframes.json"):
            json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                       "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
                       "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
                       "media": {"autoProxy": True}, "authoringSkill": "hyperframes"},
                      open(f"{self.dir}/hyperframes.json", "w"), indent=2)


p = Project(OUT)
full, split = [], []
WHOOSH = ["whoosh", "whoosh-short", "whoosh-cinematic"]


# ---------------------------------------------------------------- scenes
def photo(sid, sc):
    start, end = sc["start"], sc["end"]
    split.append((start, end))
    css = T("""#$s-box{position:absolute;left:0;top:0;width:1080px;height:${h}px;overflow:hidden;background:#111}
#$s-img{position:absolute;left:-70px;top:-50px;width:1220px;height:${ih}px;object-fit:cover;object-position:$pos}
#$s-grad{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.35) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,.1) 40%,rgba(0,0,0,.88) 84%)}
#$s-edge{position:absolute;left:0;right:0;bottom:0;height:10px;background:$red}
#$s-flash{position:absolute;inset:0;background:#fff;opacity:0}
#$s-cap{position:absolute;left:60px;right:60px;top:470px}
#$s-tag{display:inline-block;padding:10px 26px;border-radius:30px;background:$red;color:#fff;font:900 34px Inter}
#$s-big{font:900 128px/1 Inter;color:#fff;margin-top:20px;letter-spacing:-.02em;text-shadow:0 6px 30px rgba(0,0,0,.5)}
#$s-line{font:700 46px/1.2 Montserrat;color:#ececec;margin-top:16px}""",
            s=sid, pos=sc.get("pos", "50% 50%"), h=SPLIT_H, ih=SPLIT_H + 120, red=RED)
    tag = f'<span id="{sid}-tag">{esc(sc["tag"])}</span>' if sc.get("tag") else ""
    body = (f'<div id="{sid}-box"><img id="{sid}-img" src="assets/{sc["img"]}" alt=""><div id="{sid}-grad"></div>'
            f'<div id="{sid}-cap">{tag}<div id="{sid}-big">{esc(sc.get("big", ""))}</div>'
            f'<div id="{sid}-line">{esc(sc.get("line", ""))}</div></div><div id="{sid}-edge"></div><div id="{sid}-flash"></div></div>')
    d = end - start
    drift = 40 if len(split) % 2 else -40
    js = T("""tl.fromTo("#$s-box",{y:-$h},{y:0,duration:0.42,ease:"expo.out"},0);
tl.fromTo("#$s-flash",{opacity:0.85},{opacity:0,duration:0.35,ease:"power2.out"},0.05);
tl.fromTo("#$s-img",{scale:1.06,x:0,rotation:-0.6},{scale:1.2,x:$dx,rotation:0.6,duration:$d,ease:"none"},0);
tl.fromTo("#$s-big",{opacity:0,y:30,filter:"blur(10px)"},{opacity:1,y:0,filter:"blur(0px)",duration:0.3,ease:"power4.out"},0.28);
tl.fromTo("#$s-line",{opacity:0,y:20},{opacity:1,y:0,duration:0.35,ease:"power3.out"},0.55);
tl.to("#$s-box",{y:-$h,duration:0.3,ease:"power3.in"},$o);""",
           s=sid, d=f"{d:.2f}", dx=drift, o=f"{d - 0.3:.2f}", h=SPLIT_H)
    if tag:
        js += f'tl.fromTo("#{sid}-tag",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.3,ease:"power3.out"}},0.2);'
    if sc.get("roll_to"):
        js += f'roll("#{sid}-big",{sc["roll_to"]},0.28,0.9);'
        p.sfx("chime", start + 1.15, 0.16, 1.5)
    p.scene(sid, start, end, css, body, js)
    p.sfx(WHOOSH[len(split) % 3], start - 0.08, 0.3, 0.6)


def card(sid, sc):
    """Premium full-screen card: drifting gradient, film grain, slam-in number, small shake; optional chips / bars."""
    start, end = sc["start"], sc["end"]
    full.append((start, end))
    glow, color = sc.get("glow", RED), sc.get("color", "#fff")
    extra_css, extra_body, extra_js = "", "", ""
    if sc.get("chips"):
        extra_css += (f"#{sid}-chips{{position:absolute;top:1110px;left:0;right:0;display:flex;justify-content:center;gap:18px;flex-wrap:wrap;padding:0 60px}}"
                      f".{sid}-chip{{padding:16px 26px;border-radius:22px;background:rgba(255,216,77,.14);border:3px solid {YELLOW};color:{YELLOW};font:800 36px Montserrat}}"
                      f".{sid}-chip.last{{background:{YELLOW};color:#111}}")
        chips = sc["chips"]
        extra_body += f'<div id="{sid}-chips">' + "".join(
            f'<div class="{sid}-chip{" last" if k == len(chips) - 1 and str(c).startswith("=") else ""}">{esc(c)}</div>'
            for k, c in enumerate(chips)) + "</div>"
        extra_js += f'tl.fromTo(".{sid}-chip",{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.35,ease:"back.out(1.6)",stagger:0.35}},1.6);'
        for k in range(len(chips)):
            p.sfx("pop", start + 1.6 + k * 0.35, 0.3, 0.4)
    if sc.get("bars"):
        top = max(b["pct"] for b in sc["bars"]) or 1
        extra_css += (f".{sid}-lbs{{position:absolute;top:1090px;left:90px;right:90px}}"
                      f".{sid}-lb{{display:flex;align-items:center;height:52px;gap:18px}}"
                      f".{sid}-lbn{{width:330px;font:700 30px Montserrat;color:#c9c9d4;white-space:nowrap}}"
                      f".{sid}-lbt{{flex:1;height:24px}}.{sid}-lbf{{height:24px;border-radius:12px;background:#3b4566}}"
                      f".{sid}-lbp{{width:110px;text-align:right;font:800 30px Inter;color:#fff}}"
                      f".{sid}-miss .{sid}-lbn,.{sid}-miss .{sid}-lbp{{color:#ff5a63}}.{sid}-miss .{sid}-lbf{{background:{RED}}}")
        extra_body += f'<div class="{sid}-lbs">' + "".join(
            f'<div class="{sid}-lb{f" {sid}-miss" if b.get("miss") else ""}"><div class="{sid}-lbn">{esc(b["label"])}</div>'
            f'<div class="{sid}-lbt"><div class="{sid}-lbf" style="width:{max(6, b["pct"] / top * 330):.0f}px"></div></div>'
            f'<div class="{sid}-lbp">{esc(b.get("text", str(b["pct"]) + "%"))}</div></div>' for b in sc["bars"]) + "</div>"
        extra_js += (f'tl.fromTo(".{sid}-lbf",{{scaleX:0,transformOrigin:"0% 50%"}},{{scaleX:1,duration:0.5,ease:"expo.out",stagger:0.06}},0.8);'
                     f'tl.fromTo(".{sid}-miss",{{opacity:0.2}},{{opacity:1,duration:0.08,repeat:5,yoyo:true}},2.3);')
    css = T("""#$s-bg{position:absolute;inset:-200px;background:radial-gradient(circle at 30% 35%,${g}$ga 0%,rgba(0,0,0,0) 45%),radial-gradient(circle at 75% 70%,$g2 0%,rgba(0,0,0,0) 50%),$base}
#$s-grain{position:absolute;inset:0;background-image:$grain;opacity:.22;mix-blend-mode:overlay}
#$s-a{position:absolute;top:640px;left:60px;right:60px;text-align:center;font:700 44px Montserrat;color:#b8b8c4;letter-spacing:.1em}
#$s-b{position:absolute;top:730px;width:100%;text-align:center;font:900 ${bs}px/1 Inter;color:$c;letter-spacing:-.02em;text-shadow:0 0 60px ${g}88}
#$s-c{position:absolute;top:960px;left:60px;right:60px;text-align:center;font:700 50px/1.2 Montserrat;color:#fff}
""", s=sid, c=color, g=glow, grain=GRAIN, ga=sc.get("glow_alpha", "55"), g2=sc.get("glow2", "#1d2a5a88"),
       base=sc.get("base", "#05060a"), bs=180 if len(str(sc.get("big", ""))) <= 9 else 130) + extra_css
    body = (f'<div id="{sid}-bg"></div><div id="{sid}-grain"></div><div id="{sid}-a">{esc(sc.get("top", ""))}</div>'
            f'<div id="{sid}-b">{esc(sc.get("big", ""))}</div><div id="{sid}-c">{esc(sc.get("bottom", ""))}</div>' + extra_body)
    d = end - start
    js = T("""tl.fromTo("#$s-bg",{x:-60,y:0},{x:60,y:-80,duration:$d,ease:"none"},0);
tl.fromTo("#root",{opacity:0},{opacity:1,duration:0.12},0);
tl.fromTo("#$s-a",{opacity:0,y:-20},{opacity:1,y:0,duration:0.3,ease:"power3.out"},0.05);
tl.fromTo("#$s-b",{opacity:0,scale:2.1},{opacity:1,scale:1,duration:0.3,ease:"power4.in"},0.12);
tl.to("#$s-b",{x:-14,duration:0.04},0.42);tl.to("#$s-b",{x:12,duration:0.04},0.46);
tl.to("#$s-b",{x:-7,duration:0.04},0.50);tl.to("#$s-b",{x:0,duration:0.05},0.54);
tl.fromTo("#$s-c",{opacity:0,y:24},{opacity:1,y:0,duration:0.35,ease:"power3.out"},0.6);
$extra_js
tl.to("#root",{opacity:0,duration:0.15},$o);""", s=sid, d=f"{d:.2f}", o=f"{d - 0.16:.2f}", extra_js=extra_js)
    if sc.get("roll_to"):
        js += f'roll("#{sid}-b",{sc["roll_to"]},0.12,1.1,"{sc.get("prefix", "₹")}","{sc.get("suffix", "")}");'
        p.sfx("chime", start + 1.15, 0.2, 1.5)
    p.scene(sid, start, end, css, body, js)
    p.sfx("whoosh-short", start - 0.08, 0.28, 0.6)
    p.sfx("impact-bass-1", start + 0.38, 0.4, 1.5)


def badge(sid, sc):
    css = T("""#$s-w{position:absolute;left:56px;top:300px;display:flex;align-items:center;gap:22px}
#$s-n{min-width:150px;height:150px;padding:0 20px;border-radius:36px;background:$red;color:#fff;font:900 84px Inter;display:flex;align-items:center;justify-content:center;box-shadow:0 18px 40px rgba(224,34,46,.45)}
#$s-p{padding:16px 30px;border-radius:24px;background:rgba(10,12,20,.82);color:$y;font:900 64px Inter}""", s=sid, red=RED, y=YELLOW)
    pct = f'<div id="{sid}-p">{esc(sc["pct"])}</div>' if sc.get("pct") else ""
    body = f'<div id="{sid}-w"><div id="{sid}-n">#{esc(sc["n"])}</div>{pct}</div>'
    d = sc["end"] - sc["start"]
    js = T("""tl.fromTo("#$s-n",{scale:0,rotation:-20},{scale:1,rotation:0,duration:0.45,ease:"back.out(2)"},0);
tl.to("#$s-w",{opacity:0,y:-20,duration:0.25,ease:"power2.in"},$o);""", s=sid, o=f"{d - 0.25:.2f}")
    if pct:
        js += f'tl.fromTo("#{sid}-p",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.35,ease:"power3.out"}},0.18);'
    p.scene(sid, sc["start"], sc["end"], css, body, js, z=6, transparent=True)
    p.sfx("pop", sc["start"], 0.4, 0.4)


def sticker(sid, sc, k):
    side = "left:56px" if k % 2 else "right:56px"
    css = T("""#$s-w{position:absolute;$side;top:330px;max-width:820px;padding:22px 34px;border-radius:30px;background:#fff;
color:#111;font:800 50px/1.2 Montserrat;box-shadow:0 18px 50px rgba(0,0,0,.35);transform-origin:50% 100%}""", s=sid, side=side)
    d = sc["end"] - sc["start"]
    js = T("""tl.fromTo("#$s-w",{scale:0.5,opacity:0,rotation:-4},{scale:1,opacity:1,rotation:0,duration:0.4,ease:"back.out(1.8)"},0);
tl.to("#$s-w",{scale:0.8,opacity:0,duration:0.2,ease:"power2.in"},$o);""", s=sid, o=f"{d - 0.2:.2f}")
    p.scene(sid, sc["start"], sc["end"], css, f'<div id="{sid}-w">{esc(sc["text"])}</div>', js, z=6, transparent=True)
    p.sfx("click-soft", sc["start"], 0.35, 0.5)


def progress(sid, sc):
    items = sc["items"]
    s0 = sc["start"]
    segs = "".join(f'<div class="pg-s" id="pg{k}"><div class="pg-f"></div></div>' for k in range(len(items)))
    labels = "".join(f'<div class="pg-t" id="pgt{k}">{esc(it["label"])}</div>' for k, it in enumerate(items))
    css = f"""#pg-w{{position:absolute;left:56px;right:160px;top:120px;display:flex;gap:10px}}
.pg-s{{flex:1;height:12px;border-radius:6px;background:rgba(255,255,255,.28);overflow:hidden}}
.pg-f{{width:100%;height:100%;background:{YELLOW};transform-origin:0% 50%}}
.pg-t{{position:absolute;left:56px;top:146px;font:800 32px Montserrat;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.6);opacity:0}}"""
    js = 'tl.set(".pg-f",{scaleX:0},0);tl.fromTo("#pg-w",{opacity:0},{opacity:1,duration:0.3},0);'
    for k, it in enumerate(items):
        at = it["at"] - s0
        js += (f'tl.to("#pg{k} .pg-f",{{scaleX:1,duration:0.4,ease:"power2.out"}},{at:.2f});'
               f'tl.set("#pgt{k}",{{opacity:1}},{at:.2f});')
        if k:
            js += f'tl.set("#pgt{k - 1}",{{opacity:0}},{at:.2f});'
    js += f'tl.to("#pg-w,#pgt{len(items) - 1}",{{opacity:0,duration:0.3}},{sc["end"] - s0 - 0.3:.2f});'
    p.scene(sid, s0, sc["end"], css, f'<div id="pg-w">{segs}</div>{labels}', js, z=7, transparent=True)


def quote(sid, sc, extra_body):
    QS, QE = sc["start"], sc["end"]
    full.append((QS, QE))
    css = f"""#qt-bg{{position:absolute;inset:0;background:#fbfaf6;background-image:linear-gradient(#ecebe4 2px,transparent 2px),linear-gradient(90deg,#ecebe4 2px,transparent 2px);background-size:90px 90px}}
#qt-mark{{position:absolute;left:70px;top:330px;font:900 300px/1 Georgia;color:{RED}}}
.qt-l{{position:absolute;left:60px;right:60px;text-align:center;font:800 66px/1.2 Montserrat;color:#111}}
#qt-hl{{background:linear-gradient({YELLOW},{YELLOW}) no-repeat 0 85%/0% 55%;padding:0 10px}}
.acc{{color:{RED}}}"""
    acc = tuple(sc.get("accent", ()))
    body = ('<div id="qt-bg"></div><div id="qt-mark">“</div><div class="qt-l" style="top:700px">'
            + split_words(esc(sc["line1"]), "qt-w", acc) + '</div><div class="qt-l" style="top:900px"><span id="qt-hl">'
            + split_words(esc(sc["line2"]), "qt-w2", acc) + "</span></div>")
    n1 = len(sc["line1"].split())
    t2 = 0.1 + n1 * 0.12 + 0.4
    hl = t2 + len(sc["line2"].split()) * 0.13 + 0.2
    js = f"""tl.fromTo("#qt-mark",{{opacity:0,scale:0.4}},{{opacity:1,scale:1,duration:0.4,ease:"back.out(2)"}},0);
words(".qt-w",0.1,0.12); words(".qt-w2",{t2:.2f},0.13);
tl.fromTo("#qt-hl",{{backgroundSize:"0% 55%"}},{{backgroundSize:"100% 55%",duration:0.45,ease:"power2.inOut"}},{hl:.2f});
tl.to("#root",{{opacity:0,duration:0.15}},{QE - QS - 0.16:.2f});"""
    p.scene(sid, QS, QE, css, body, js)
    p.sfx("key-press", QS + 0.05, 0.25, 0.4)
    p.sfx("sparkle", QS + hl, 0.25, 1.2)
    if sc.get("bubble", True):
        p.extra.append("#pip{position:absolute;left:350px;top:1300px;width:380px;height:380px;border-radius:50%;z-index:8;"
                       "border:8px solid #fff;object-fit:cover;object-position:50% 50%;box-shadow:0 24px 60px rgba(0,0,0,.25);"
                       "filter:contrast(1.07) saturate(1.12)}")
        extra_body.append(f'<video id="pip" class="clip" src="assets/cut.mp4" data-start="{QS}" data-duration="{QE - QS:.2f}" '
                          f'data-media-start="{QS}" data-track-index="7" muted playsinline></video>')
        p.root_js.append(f'tl.fromTo("#pip",{{scale:0,opacity:0}},{{scale:1,opacity:1,duration:0.4,ease:"back.out(1.7)"}},{QS + 0.3:.2f});')


def cta(sid, sc):
    css = T("""#$s-card{position:absolute;left:48px;right:48px;top:300px;padding:30px 36px;border-radius:28px;
background:rgba(12,14,22,.82);backdrop-filter:blur(22px);border-left:10px solid $a}
#$s-k{font:800 30px Montserrat;letter-spacing:.08em;text-transform:uppercase;color:#ff6b6f}
#$s-l{font:800 52px/1.15 Montserrat;color:#fff;margin-top:10px}""", s=sid, a=RED)
    body = f'<div id="{sid}-card"><div id="{sid}-k">{esc(sc["kicker"])}</div><div id="{sid}-l">{esc(sc["line"])}</div></div>'
    d = sc["end"] - sc["start"]
    js = T("""tl.fromTo("#$s-card",{opacity:0,y:40},{opacity:1,y:0,duration:0.4,ease:"power2.out"},0);
tl.to("#$s-card",{opacity:0,y:20,duration:0.35,ease:"power2.in"},$out);""", s=sid, out=f"{d - 0.4:.2f}")
    p.scene(sid, sc["start"], sc["end"], css, body, js, z=6, transparent=True)
    p.sfx("notification", sc["start"], 0.25, 1.0)


def end_card(sid, sc):
    start, end = sc["start"], DUR
    full.append((start, end))
    thumbs = sc.get("thumbs") or []
    if thumbs:  # real 16:9 thumbnails, stacked
        lay = """#$s-t{top:300px}.$s-slot{left:130px;width:820px;height:461px;border:none;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.18)}
#$s-a{top:500px}#$s-b{top:1090px}.$s-cap{left:130px;width:820px;text-align:left}
#$s-ca{top:975px}#$s-cb{top:1565px}#$s-sub{top:1680px}"""
    else:
        lay = """.$s-slot{top:760px;width:420px;height:560px}#$s-a{left:60px}#$s-b{right:60px}
.$s-cap{top:1340px;width:420px;text-align:center}#$s-ca{left:60px}#$s-cb{right:60px}#$s-sub{top:1060px}"""
    css = T("""#$s-bg{position:absolute;inset:0;background:#fff}
#$s-t{position:absolute;top:520px;width:100%;text-align:center;font:italic 700 92px "Playfair Display";color:#111}
.$s-slot{position:absolute;border-radius:24px;background:#e9e9ee;border:3px solid #d5d5dc}
.$s-cap{position:absolute;font:700 30px Montserrat;color:#777}
#$s-sub{position:absolute;left:390px;width:300px;height:96px;border-radius:48px;background:$red;
color:#fff;font:900 34px Montserrat;display:flex;align-items:center;justify-content:center}
""" + lay, s=sid, red=RED)
    img = [f'<img src="assets/{f}" alt="" style="width:100%;height:100%;object-fit:cover">' for f in thumbs] + ["", ""]
    body = T("""<div id="$s-bg"></div><div id="$s-t">Thank you for watching!</div>
<div class="$s-slot" id="$s-a">$ta</div><div class="$s-slot" id="$s-b">$tb</div>
<div class="$s-cap" id="$s-ca">MY SUGGESTION</div><div class="$s-cap" id="$s-cb">WATCH NEXT</div>
<div id="$s-sub">SUBSCRIBE</div>""", s=sid, ta=img[0], tb=img[1])
    js = T("""tl.fromTo("#$s-t",{opacity:0,filter:"blur(10px)"},{opacity:1,filter:"blur(0px)",duration:0.3,ease:"power4.out"},0.1);
tl.fromTo(".$s-slot",{opacity:0,y:60},{opacity:1,y:0,duration:0.5,ease:"expo.out",stagger:0.08},0.25);
tl.fromTo("#$s-sub",{scale:0.4,opacity:0},{scale:1,opacity:1,duration:0.45,ease:"back.out(1.6)"},0.3);""", s=sid)
    p.scene(sid, start, end, css, body, js, z=9)
    p.sfx("whoosh", start - 0.08, 0.3, 0.6)


def captions(chunks, hide, split, mode):
    """Karaoke captions: 2-4 words, the spoken word turns yellow and pops; numbers yellow, negatives red."""
    if mode == "off":
        return

    def inside(t, spans):
        return any(s - 0.05 <= t < e for s, e in spans)
    stop = min([s for s, e in hide if e >= DUR - 0.01] or [DUR])
    css = f""".cc{{position:absolute;left:40px;right:40px;text-align:center;visibility:hidden;
font:900 66px/1.1 Montserrat;color:#fff;-webkit-text-stroke:12px #000;paint-order:stroke fill;
text-shadow:0 6px 18px rgba(0,0,0,.55)}}
.cw{{display:inline-block;margin:0 16px;transform-origin:50% 70%}}
.cw.num{{color:{YELLOW};font-size:84px}}.cw.neg{{color:#ff4b55}}"""
    groups, body, js, g_start = [], [], [], 0.0
    for i, c in enumerate(chunks):
        mid = (c["start"] + min(c["end"], c["words"][-1]["e"])) / 2
        if c["start"] >= stop or inside(mid, hide):
            continue
        if mode == "keywords" and not any(w["kind"] for w in c["words"]):
            continue
        top = CAP_SPLIT if inside(mid, split) else CAP_FACE
        ws = " ".join(f'<span class="cw {w["kind"]}" id="c{i}w{j}">{esc(w["t"])}</span>' for j, w in enumerate(c["words"]))
        body.append(f'<div class="cc" id="c{i}" style="top:{top}px">{ws}</div>')
        js.append(f'tl.set("#c{i}",{{visibility:"visible"}},{c["start"]:.3f});'
                  f'tl.fromTo("#c{i}",{{scale:0.86,y:14}},{{scale:1,y:0,duration:0.14,ease:"back.out(2)"}},{c["start"]:.3f});'
                  f'tl.set("#c{i}",{{visibility:"hidden"}},{min(c["end"], stop):.3f});')
        for j, w in enumerate(c["words"]):
            base = YELLOW if w["kind"] == "num" else "#ff4b55" if w["kind"] == "neg" else "#fff"
            on = "#fff" if w["kind"] == "num" else YELLOW
            js.append(f'tl.set("#c{i}w{j}",{{color:"{on}",scale:1.12}},{w["s"]:.3f});'
                      f'tl.set("#c{i}w{j}",{{color:"{base}",scale:1}},{w["e"]:.3f});')
        if len(body) >= 30:
            groups.append((g_start, min(c["end"], stop), body, js))
            body, js, g_start = [], [], min(c["end"], stop)
    if body:
        groups.append((g_start, stop, body, js))
    for k, (a, b, body, js) in enumerate(groups):
        # times above are absolute; shift them to the sub-composition's own clock
        js = [re.sub(r"\},(\d+\.\d{3})\);", lambda m: "},%.3f);" % (float(m.group(1)) - a), x) for x in js]
        p.scene(f"captions{k + 1}", a, b, css, "\n".join(body), "\n".join(js), z=8, transparent=True)


# ---------------------------------------------------------------- assemble
p.extra.append("#face{filter:contrast(1.07) saturate(1.12) brightness(1.02)}")
p.extra.append("#vig{position:absolute;inset:0;z-index:2;pointer-events:none;"
               "background:radial-gradient(ellipse 75% 60% at 50% 45%,rgba(0,0,0,0) 55%,rgba(0,0,0,.42) 100%)}")
extra_body = [f'<div id="vig" class="clip" data-start="0" data-duration="{DUR}" data-track-index="8"></div>']
if plan.get("watermark"):
    p.extra.append("#wm{position:absolute;top:190px;right:46px;z-index:20;font:900 46px Inter;color:#fff;"
                   "letter-spacing:-.04em;opacity:.85;text-shadow:0 2px 12px rgba(0,0,0,.4)}")
    extra_body.append(f'<div id="wm" class="clip" data-start="0" data-duration="{DUR}" data-track-index="9">{esc(plan["watermark"])}</div>')

counts = {}
# a progress bar never runs into the next full-screen card after its last item
for pg in [s for s in plan["scenes"] if s["type"] == "progress"]:
    last = pg["items"][-1]["at"]
    nxt = [s["start"] for s in plan["scenes"] if s["type"] in ("card", "quote", "end") and s["start"] > last + 4]
    if nxt:
        pg["end"] = min(pg["end"], min(nxt))
for sc in sorted(plan["scenes"], key=lambda s: s["start"]):
    t = sc["type"]
    counts[t] = counts.get(t, 0) + 1
    sid = f"{t}{counts[t]}"
    if t == "photo":
        photo(sid, sc)
    elif t == "card":
        card(sid, sc)
    elif t == "badge":
        badge(sid, sc)
    elif t == "sticker":
        sticker(sid, sc, counts[t])
    elif t == "progress":
        progress(sid, sc)
    elif t == "quote":
        quote(sid, sc, extra_body)
    elif t == "cta":
        cta(sid, sc)
    elif t == "end":
        end_card(sid, sc)
    else:
        raise SystemExit(f"unknown scene type {t!r}")
for s in plan.get("sfx", []):
    p.sfx(s["name"], s["at"], s.get("vol", 0.3), s.get("dur", 1.0))

# the face slides down once per run of back-to-back photos
runs = []
for a, b in sorted(split):
    if runs and a - runs[-1][1] < 0.1:
        runs[-1][1] = b
    else:
        runs.append([a, b])
for a, b in runs:
    p.root_js.append(f'tl.to("#camwrap",{{y:{FACE_DY},duration:0.42,ease:"expo.out"}},{a:.2f});'
                     f'tl.to("#camwrap",{{y:0,duration:0.3,ease:"power3.in"}},{b - 0.3:.2f});')

captions(json.load(open(plan["captions"], encoding="utf-8")), full, split, plan.get("captions_mode", "full"))
p.punch_ins(full)
p.write(extra_body="\n".join(extra_body))
print(f"built {OUT}: {counts}")
