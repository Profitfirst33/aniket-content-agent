#!/usr/bin/env python3
"""Data-driven nick_saraev-style reel builder (style: ../nick-style-guide.md).

usage: build_reel.py <job_dir>
Reads   <job>/spec.json   scene plan with start/end times on the cut timeline
        <job>/words.json  [[text, start, end], ...] caption words (Roman Hinglish)
        <job>/edit/assets face.mp4, face_cutout.webm, voice.wav, music.wav, sfx/, plus any images/videos the spec names
Writes  <job>/edit/index.html + compositions/*.html

spec.json:
{
  "duration": 27.95,
  "keywords": ["agent", "viral"],          # caption words drawn in lime italic
  "scenes": [ {"id": "s1", "start": 0, "end": 4.0, "face": "card|none|full", "bg": "light|dark",
               "type": "<scene type>", "line1": "black headline (optional)", "box": "lime box text", ...type fields} ]
}
Scene types and their fields:
  browser_image  url, img                      website/app screenshot in a browser frame (Ken Burns)
  terminal       title, lines: [[prefix, text], ...]   lines appear one by one
  tiles          url, items: [{emoji, text}] x3        topic cards pop in
  doc            file, lines: [text, ...]              lines type in
  notification   app, title, sub                       phone notification drops in
  roles          items: [4 texts], result              4 chips = 1 result bar
  bigstat        big, sub, lines: [text, ...]          dark: status card + huge lime number
  compare        top: {src, label}, bottom: {src, label}   two video cards (dark)
  cta            (no fields)                           full-screen face, CTA caption only
"""
import json, os, sys, html

LIME = "#D9F23E"
FACE_Y = 880        # face video translateY in card mode (head top ~y 1130)
CARD_TOP = 1490     # grey card top; the head pops out above it

JOB = os.path.abspath(sys.argv[1])
OUT = f"{JOB}/edit"
SPEC = json.load(open(f"{JOB}/spec.json"))
WORDS = json.load(open(f"{JOB}/words.json"))
DUR = float(SPEC["duration"])
SCENES = SPEC["scenes"]
KEYWORDS = {k.lower().strip('."?') for k in SPEC.get("keywords", [])}
SFX = []


def sfx(name, at, vol=0.35, dur=0.8):
    SFX.append((name, at, vol, dur))


E = html.escape

BASE_CSS = f"""
#root{{position:absolute;inset:0;overflow:hidden;font-family:Inter,sans-serif;color:#0E0E0E}}
.hl{{position:absolute;left:0;right:0;text-align:center}}
.hl1{{font:900 76px/1.05 Inter;letter-spacing:-1.5px}}
.hl1 .w{{display:inline-block;margin:0 9px}}
.box{{display:inline-block;background:{LIME};padding:6px 30px 14px;border-radius:6px;
  font:italic 800 92px/1.08 'Playfair Display';color:#0E0E0E;letter-spacing:-1px;box-shadow:0 10px 30px rgba(140,170,20,.25)}}
.box .w{{display:inline-block;margin:0 8px}}
.card{{position:absolute;border-radius:30px;border:6px solid {LIME};overflow:hidden;background:#111;
  box-shadow:0 0 0 2px rgba(217,242,62,.35),0 0 46px rgba(217,242,62,.45),0 28px 70px rgba(0,0,0,.28)}}
.chrome{{position:absolute;left:0;right:0;top:0;height:64px;background:#F3F3F1;display:flex;align-items:center;
  padding:0 22px;gap:12px;border-bottom:1px solid #ddd}}
.dot{{width:17px;height:17px;border-radius:50%}}
.url{{flex:1;margin:0 60px;height:38px;border-radius:19px;background:#fff;border:1px solid #ddd;
  font:600 22px/38px Inter;color:#333;text-align:center;white-space:nowrap;overflow:hidden}}
.chip{{position:absolute;background:{LIME};color:#0E0E0E;font:900 26px/1 Inter;padding:10px 16px;border-radius:10px;
  letter-spacing:.5px;text-transform:uppercase}}
"""

DOTS = ('<span class="dot" style="background:#FF5F57"></span><span class="dot" style="background:#FEBC2E"></span>'
        '<span class="dot" style="background:#28C840"></span>')


def chrome(url):
    return f'<div class="chrome">{DOTS}<div class="url">🔒 {E(url)}</div></div>'


def spans(text, prefix):
    return " ".join(f'<span class="w" id="{prefix}{i}">{E(w)}</span>' for i, w in enumerate(text.split()))


def headline(sid, line1, box, top=230):
    h, js, t = "", [], 0.05
    if line1:
        h += f'<div class="hl hl1" style="top:{top}px">{spans(line1, sid + "-a")}</div>'
        for i, _ in enumerate(line1.split()):
            js.append(f'tl.fromTo("#{sid}-a{i}",{{opacity:0,y:24,filter:"blur(8px)"}},{{opacity:1,y:0,filter:"blur(0px)",duration:.28,ease:"power3.out"}},{t:.2f});')
            t += 0.12
        top += 100
    if box:
        h += f'<div class="hl" style="top:{top}px"><span class="box" id="{sid}-box">{spans(box, sid + "-b")}</span></div>'
        js.append(f'tl.fromTo("#{sid}-box",{{scaleX:0.2,opacity:0}},{{scaleX:1,opacity:1,duration:.32,ease:"back.out(1.6)"}},{t:.2f});')
        for i, _ in enumerate(box.split()):
            js.append(f'tl.fromTo("#{sid}-b{i}",{{opacity:0,y:18}},{{opacity:1,y:0,duration:.22,ease:"power2.out"}},{t + .12 + i * .13:.2f});')
        sfx("pop", t + 0.05, 0.25, 0.4)
    return h, js


def card_in(sel, at=0.15):
    return (f'tl.fromTo("{sel}",{{opacity:0,scale:.9,filter:"blur(14px)"}},'
            f'{{opacity:1,scale:1,filter:"blur(0px)",duration:.42,ease:"power3.out"}},{at:.2f});')


def demo_box(sc):
    """Card rectangle: smaller when the avatar card is on screen."""
    if sc["face"] == "card":
        return 90, 520, 900, 470
    return 60, 440, 960, 700


# ------------------------------------------------------------ scene types
def t_browser_image(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    h = (f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px">{chrome(sc.get("url", ""))}'
         f'<img id="{sid}-img" src="assets/{E(sc["img"])}" style="position:absolute;left:0;top:64px;width:{w}px;height:{hgt - 64}px;object-fit:cover;object-position:50% 0"></div>')
    js = [card_in(f"#{sid}-card", .2), f'tl.fromTo("#{sid}-img",{{scale:1}},{{scale:1.07,duration:{d:.2f},ease:"none"}},0);']
    sfx("whoosh", 0.15, 0.3)
    return h, js


def t_terminal(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    rows, js = "", [card_in(f"#{sid}-card", .2)]
    for i, (p, t) in enumerate(sc["lines"][:7]):
        col = LIME if p in ("$", "→", ">") else "#7CFF9B"
        rows += (f'<div id="{sid}-l{i}" style="font:600 32px/1.35 \'JetBrains Mono\';color:#E8E8E8;margin-bottom:10px;white-space:nowrap;overflow:hidden">'
                 f'<span style="color:{col};margin-right:18px">{E(p)}</span>{E(t)}</div>')
        at = 0.45 + i * min(0.4, (d - 1.2) / max(1, len(sc["lines"])))
        js.append(f'tl.fromTo("#{sid}-l{i}",{{opacity:0,x:-20}},{{opacity:1,x:0,duration:.2,ease:"power2.out"}},{at:.2f});')
        sfx("key-press" if i == 0 else "click-soft", at, 0.22, 0.4)
    h = (f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px;background:#0F1012">'
         f'<div style="position:absolute;left:0;right:0;top:0;height:60px;background:#1B1C1F;display:flex;align-items:center;padding:0 22px;gap:12px">'
         f'{DOTS}<span style="flex:1;text-align:center;font:600 22px Inter;color:#888">{E(sc.get("title", "terminal"))}</span></div>'
         f'<div style="position:absolute;left:46px;top:100px;right:40px">{rows}</div></div>')
    return h, js


def t_tiles(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    items = sc["items"][:3]
    tw = (w - 60 - 20 * (len(items) - 1)) // len(items)
    bgs = ["#F2EEE6", "#EAF3D1", "#E6EEF7"]
    tiles, js = "", [card_in(f"#{sid}-card", .2)]
    for i, it in enumerate(items):
        tiles += (f'<div id="{sid}-t{i}" style="position:absolute;left:{30 + i * (tw + 20)}px;top:96px;width:{tw}px;height:{hgt - 130}px;border-radius:20px;'
                  f'background:{bgs[i]};display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px">'
                  f'<div style="font-size:84px">{E(it.get("emoji", "🔥"))}</div><div style="font:900 34px/1.15 Inter;text-align:center;padding:0 16px">{E(it["text"])}</div></div>')
        js.append(f'tl.fromTo("#{sid}-t{i}",{{opacity:0,y:40,scale:.9}},{{opacity:1,y:0,scale:1,duration:.3,ease:"back.out(1.7)"}},{.55 + i * .35:.2f});')
        sfx("pop", .55 + i * .35, 0.25, 0.4)
    h = f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px;background:#fff">{chrome(sc.get("url", ""))}{tiles}</div>'
    return h, js


def t_doc(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    rows, js = "", [card_in(f"#{sid}-card", .15)]
    lines = sc["lines"][:7]
    step = min(0.3, (d - 1.0) / max(1, len(lines)))
    for i, t in enumerate(lines):
        rows += f'<div id="{sid}-l{i}" style="font:600 31px/1.5 \'JetBrains Mono\';color:#222;white-space:pre">{E(t)}</div>'
        js.append(f'tl.fromTo("#{sid}-l{i}",{{clipPath:"inset(0 100% 0 0)"}},{{clipPath:"inset(0 0% 0 0)",duration:{step:.2f},ease:"none"}},{.4 + i * step:.2f});')
    h = (f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px;background:#FBFBF8">'
         f'{chrome(sc.get("file", "script.md"))}<div style="position:absolute;left:44px;top:100px;right:30px">{rows}</div></div>')
    sfx("typing", 0.4, 0.22, min(1.5, d - 0.6))
    return h, js


def t_notification(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    h = (f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px;background:linear-gradient(160deg,#20232B,#0E0F13)">'
         f'<div id="{sid}-n" style="position:absolute;left:60px;right:60px;top:{hgt // 2 - 115}px;background:rgba(255,255,255,.96);border-radius:28px;padding:30px 34px;'
         f'display:flex;gap:26px;align-items:center;box-shadow:0 20px 50px rgba(0,0,0,.4)">'
         f'<div style="width:96px;height:96px;flex:none;border-radius:24px;background:{LIME};display:flex;align-items:center;justify-content:center;font-size:56px">🤖</div>'
         f'<div><div style="font:800 30px Inter;color:#666">{E(sc.get("app", "Content Agent"))} · now</div>'
         f'<div style="font:900 40px/1.2 Inter;color:#111;margin-top:6px">{E(sc["title"])}</div>'
         f'<div style="font:600 28px Inter;color:#555;margin-top:6px">{E(sc.get("sub", ""))}</div></div></div></div>')
    js = [card_in(f"#{sid}-card", .15), f'tl.fromTo("#{sid}-n",{{y:-160,opacity:0}},{{y:0,opacity:1,duration:.45,ease:"back.out(1.5)"}},.55);']
    sfx("notification", 0.6, 0.35, 1.0)
    return h, js


def t_roles(sid, sc, d):
    x, y, w, hgt = demo_box(sc)
    chips, js = "", [card_in(f"#{sid}-card", .15)]
    cw = (w - 80 - 30) // 2
    for i, r in enumerate(sc["items"][:4]):
        chips += (f'<div id="{sid}-r{i}" style="position:absolute;left:{40 + (i % 2) * (cw + 30)}px;top:{60 + (i // 2) * 120}px;width:{cw}px;height:96px;'
                  f'border-radius:18px;background:#F1F1EE;font:800 36px/96px Inter;text-align:center;color:#222">{E(r)}</div>')
        js.append(f'tl.fromTo("#{sid}-r{i}",{{opacity:0,scale:.8}},{{opacity:1,scale:1,duration:.22,ease:"back.out(2)"}},{.4 + i * .18:.2f});')
        sfx("pop", .4 + i * .18, 0.22, 0.4)
    h = (f'<div class="card" id="{sid}-card" style="left:{x}px;top:{y}px;width:{w}px;height:{hgt}px;background:#fff">{chips}'
         f'<div id="{sid}-one" style="position:absolute;left:40px;right:40px;top:{hgt - 150}px;height:110px;border-radius:20px;background:#0E0E0E;'
         f'font:900 50px/110px Inter;text-align:center;color:{LIME}">{E(sc["result"])}</div></div>')
    js.append(f'tl.fromTo("#{sid}-one",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:"back.out(1.6)"}},1.2);')
    sfx("impact-bass-2", 1.2, 0.35, 1.2)
    return h, js


def t_bigstat(sid, sc, d):
    rows = "".join(f'<div style="font:600 30px/1.5 \'JetBrains Mono\';color:{"#7CFF9B" if i == 0 else "#DADADA"};white-space:nowrap;overflow:hidden">{E(s)}</div>'
                   for i, s in enumerate(sc.get("lines", [])[:5]))
    h = ""
    if rows:
        h += (f'<div class="card" id="{sid}-card" style="left:90px;top:380px;width:900px;height:420px;background:rgba(12,13,15,.92)">'
              f'<div style="position:absolute;left:44px;top:60px;right:30px">{rows}</div></div>')
    h += (f'<div class="hl" style="top:880px"><span id="{sid}-big" style="display:inline-block;font:900 230px/1 Inter;color:{LIME};'
          f'letter-spacing:-6px;text-shadow:0 0 60px rgba(217,242,62,.55)">{E(sc["big"])}</span></div>'
          f'<div class="hl" style="top:1130px;font:800 44px Inter;color:#fff" id="{sid}-sub">{E(sc.get("sub", ""))}</div>')
    js = ([card_in(f"#{sid}-card", .1)] if rows else []) + [
        f'tl.fromTo("#{sid}-big",{{scale:.4,opacity:0}},{{scale:1,opacity:1,duration:.45,ease:"back.out(2)"}},{.85 if rows else .2});',
        f'tl.fromTo("#{sid}-sub",{{opacity:0,y:20}},{{opacity:.9,y:0,duration:.3}},{1.15 if rows else .5});']
    sfx("whoosh-cinematic", 0.0, 0.35, 1.2); sfx("impact-bass-1", .9 if rows else .25, 0.4, 1.4)
    return h, js


def t_compare(sid, sc, d):
    h, js = "", []
    for i, key in enumerate(("top", "bottom")):
        it, top = sc[key], (250, 830)[i]
        h += (f'<div class="card" id="{sid}-c{i}" style="left:140px;top:{top}px;width:800px;height:540px;background:#000">'
              f'<video id="{sid}-v{i}" class="clip" src="assets/{E(it["src"])}" data-start="0" data-duration="{d:.2f}" data-track-index="{2 + i}" muted playsinline '
              f'style="position:absolute;left:0;top:-160px;width:800px;height:1422px;object-fit:cover"></video>'
              f'<div class="chip" style="right:18px;top:18px;{"background:#fff" if i == 0 else ""}">{E(it["label"])}</div></div>')
        js.append(card_in(f"#{sid}-c{i}", (.1, .55)[i]))
    sfx("whoosh", 0.05, 0.3); sfx("whoosh-short", 0.5, 0.3)
    return h, js


def t_cta(sid, sc, d):
    sfx("notification", 0.85, 0.3, 1.0)
    return "", []


TYPES = {k[2:]: v for k, v in globals().items() if k.startswith("t_")}


def write_scene(sc):
    sid, d = sc["id"], sc["end"] - sc["start"]
    h0, js0 = ("", [])
    if sc["type"] not in ("cta", "bigstat", "compare"):
        top = 230 if sc.get("line1") else 240
        h0, js0 = headline(sid, sc.get("line1", ""), sc.get("box", ""), top)
    before = len(SFX)
    body, js = TYPES[sc["type"]](sid, sc, d)
    for k in range(before, len(SFX)):
        n, at, v, du = SFX[k]
        SFX[k] = (n, at, v, du)
    js = js0 + js
    if sc["type"] != "cta":
        js.append(f'tl.to("#{sid}-wrap",{{opacity:0,filter:"blur(12px)",scale:1.02,duration:.2,ease:"power2.in"}},{d - 0.2:.2f});')
    doc = f"""<template>
<style>{BASE_CSS}</style>
<div id="root" data-composition-id="{sid}" data-width="1080" data-height="1920">
<div id="{sid}-wrap" style="position:absolute;inset:0" data-layout-allow-overlap>
{h0}
{body}
</div>
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["{sid}"] = tl;
</script>
</template>
"""
    open(f"{OUT}/compositions/{sid}.html", "w").write(doc)


# ------------------------------------------------------------ captions
def mode_at(t):
    for sc in SCENES:
        if sc["start"] <= t < sc["end"]:
            return sc["face"], sc["bg"], sc["type"]
    return "full", "none", "cta"


def is_kw(w):
    return w.lower().strip('."?,!') in KEYWORDS


def caption_groups():
    groups, cur = [], []
    starts = [sc["start"] for sc in SCENES]
    for i, w in enumerate(WORDS):
        cur.append(w)
        nxt = WORDS[i + 1][1] if i + 1 < len(WORDS) else None
        brk = (len(cur) >= 2 or w[0].endswith((".", "?", "!", ",")) or is_kw(w[0])
               or (nxt is not None and any(w[2] - 0.06 <= s <= nxt + 0.01 for s in starts)))
        if brk:
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    return groups


def write_captions():
    groups = caption_groups()
    css = f"""
#root{{position:absolute;inset:0;overflow:visible}}
.cg{{position:absolute;left:40px;right:40px;text-align:center;visibility:hidden;font:900 84px/1.1 Inter;letter-spacing:-1px}}
.cg .w{{display:inline-block;margin:0 12px}}
.cg .k{{font:italic 800 96px/1 'Playfair Display';color:{LIME}}}
.cg.light{{color:#0E0E0E}}
.cg.light .k{{-webkit-text-stroke:3px #0E0E0E;paint-order:stroke fill}}
.cg.dark{{color:#fff;text-shadow:0 6px 24px rgba(0,0,0,.6)}}
.cg.full{{color:#fff;-webkit-text-stroke:10px #000;paint-order:stroke fill;text-shadow:0 8px 30px rgba(0,0,0,.6)}}
.cg.full .k{{text-shadow:0 0 30px rgba(217,242,62,.9)}}
"""
    divs, js = [], []
    for gi, g in enumerate(groups):
        s, e = g[0][1], g[-1][2]
        face, bg, typ = mode_at(s + 0.01)
        if face == "card":
            top, cls = 1000, "light"
        elif face == "full":
            top, cls = 1240, "full"
        elif bg == "dark":
            top, cls = (1395 if typ == "compare" else 1260), "dark"
        else:
            top, cls = 1205, "light"
        sp = " ".join(f'<span class="w{" k" if is_kw(w[0]) else ""}">{E(w[0].rstrip(".,!"))}</span>' for w in g)
        divs.append(f'<div class="cg {cls}" id="g{gi}" style="top:{top}px">{sp}</div>')
        nxt = groups[gi + 1][0][1] if gi + 1 < len(groups) else DUR
        end = min(max(e + 0.05, s + 0.35), nxt, DUR - 0.01)
        js.append(f'tl.set("#g{gi}",{{visibility:"visible",opacity:1}},{s:.2f});')
        js.append(f'tl.fromTo("#g{gi}",{{scale:.8,y:16}},{{scale:1,y:0,duration:.16,ease:"back.out(2.2)"}},{s:.2f});')
        js.append(f'tl.set("#g{gi}",{{opacity:0,visibility:"hidden"}},{end:.2f});')
    doc = f"""<template>
<style>{css}</style>
<div id="root" data-composition-id="captions" data-width="1080" data-height="1920" data-layout-allow-overflow>
{chr(10).join(divs)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["captions"] = tl;
</script>
</template>
"""
    open(f"{OUT}/compositions/captions.html", "w").write(doc)


# ------------------------------------------------------------ root
def write_root():
    hosts, darks, js = [], "", []
    for i, sc in enumerate(SCENES):
        s, e = sc["start"], sc["end"]
        hosts.append(f'<div id="{sc["id"]}" data-composition-id="{sc["id"]}" data-composition-src="compositions/{sc["id"]}.html" '
                     f'data-start="{s:.2f}" data-duration="{e - s:.2f}" data-track-index="{20 + i % 4}" data-track-kind="graphics" '
                     f'data-width="1080" data-height="1920" style="z-index:20"></div>')
        js.append(f'tl.to("#rig",{{opacity:{1 if sc["face"] == "card" else 0},y:{0 if sc["face"] == "card" else 120},duration:.3,ease:"power3.out"}},{max(0, s - 0.05):.2f});')
        js.append(f'tl.to("#fullwrap",{{opacity:{1 if sc["face"] == "full" else 0},duration:.25}},{max(0, s - 0.05):.2f});')
        if sc["face"] == "card":
            js.append(f'tl.fromTo("#rigcam",{{scale:1.0}},{{scale:1.03,duration:{e - s:.2f},ease:"none"}},{s:.2f});')
        if sc["face"] == "full":
            js.append(f'tl.fromTo("#fullcam",{{scale:1.0}},{{scale:1.1,duration:{e - s:.2f},ease:"none"}},{s:.2f});')
        if sc["bg"] == "dark":
            darks += (f'<video id="bg-{sc["id"]}" class="clip" src="assets/dark_bg.mp4" data-start="{s:.2f}" data-duration="{e - s:.2f}" '
                      f'data-media-start="{s:.2f}" data-track-index="3" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;z-index:2"></video>')
    first = SCENES[0]["face"]
    js.insert(0, f'tl.set("#rig",{{opacity:{1 if first == "card" else 0}}},0);tl.set("#fullwrap",{{opacity:{1 if first == "full" else 0}}},0);')

    audio = [f'<audio id="voice" class="clip" src="assets/voice.wav" data-start="0" data-duration="{DUR}" data-track-index="40" data-volume="1"></audio>',
             f'<audio id="music" class="clip" src="assets/music.wav" data-start="0" data-duration="{DUR}" data-track-index="41" data-volume="0.22"></audio>']
    for n, (name, at, vol, du) in enumerate(SFX):
        if 0 <= at < DUR - 0.1:
            audio.append(f'<audio id="fx{n}" class="clip" src="assets/sfx/{name}.mp3" data-start="{at:.2f}" data-duration="{min(du, DUR - at):.2f}" '
                         f'data-track-index="{42 + n % 6}" data-volume="{vol}"></audio>')

    doc = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:#EDEFEE}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden}}
#paper{{position:absolute;inset:0;z-index:0;background:
  radial-gradient(ellipse 60% 40% at 20% 8%,rgba(0,0,0,.07),transparent 70%),
  radial-gradient(ellipse 50% 35% at 85% 95%,rgba(0,0,0,.05),transparent 70%),#EDEFEE}}
#leaf{{position:absolute;left:-120px;top:-160px;width:760px;height:760px;z-index:1;opacity:.13}}
#grain{{position:absolute;inset:0;z-index:1;opacity:.22;mix-blend-mode:multiply}}
#rig{{position:absolute;inset:0;z-index:10}}
#rigcam{{position:absolute;inset:0;transform-origin:50% 100%}}
#cardbox{{position:absolute;left:40px;right:40px;top:{CARD_TOP}px;bottom:-40px;border-radius:44px;overflow:hidden;background:#D6D8DA}}
#facecard{{position:absolute;left:-40px;top:{FACE_Y - CARD_TOP}px;width:1080px;height:1920px;object-fit:cover}}
#popwrap{{position:absolute;left:0;right:0;top:0;height:{CARD_TOP + 4}px;overflow:hidden}}
#facecut{{position:absolute;left:0;top:{FACE_Y}px;width:1080px;height:1920px;object-fit:cover}}
#fullwrap{{position:absolute;inset:0;z-index:11;opacity:0}}
#fullcam{{position:absolute;inset:0;transform-origin:50% 35%}}
#facefull{{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover}}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="1080" data-height="1920">
<div id="paper"></div>
<svg id="leaf" viewBox="0 0 200 200" data-layout-ignore><g fill="#000">
<path d="M100 100 C60 70 30 40 10 5 C45 25 75 55 100 100Z"/><path d="M100 100 C70 90 30 85 0 70 C40 65 75 75 100 100Z"/>
<path d="M100 100 C85 60 80 30 85 0 C100 35 105 65 100 100Z"/><path d="M100 100 C120 65 140 40 175 20 C150 55 125 80 100 100Z"/>
<path d="M100 100 C75 110 45 125 15 150 C40 120 70 105 100 100Z"/></g></svg>
<svg id="grain" width="1080" height="1920" data-layout-ignore><filter id="nz"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7"/><feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(#nz)"/></svg>
{darks}
<div id="rig" data-layout-allow-overflow><div id="rigcam">
  <div id="cardbox"><video id="facecard" class="clip" src="assets/face.mp4" data-start="0" data-duration="{DUR}" data-track-index="5" muted playsinline></video></div>
  <div id="popwrap"><video id="facecut" class="clip" src="assets/face_cutout.webm" data-start="0" data-duration="{DUR}" data-track-index="6" muted playsinline data-layout-allow-occlusion></video></div>
</div></div>
<div id="fullwrap"><div id="fullcam"><video id="facefull" class="clip" src="assets/face.mp4" data-start="0" data-duration="{DUR}" data-track-index="7" muted playsinline></video></div></div>
{chr(10).join(hosts)}
<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{DUR}" data-track-index="30" data-track-kind="captions" data-width="1080" data-height="1920" style="z-index:30"></div>
{chr(10).join(audio)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    open(f"{OUT}/index.html", "w").write(doc)


def validate():
    errs, prev = [], 0.0
    for sc in SCENES:
        if sc["type"] not in TYPES:
            errs.append(f'{sc["id"]}: unknown type {sc["type"]}')
        if abs(sc["start"] - prev) > 0.02:
            errs.append(f'{sc["id"]}: starts at {sc["start"]} but previous scene ended at {prev}')
        if sc["end"] - sc["start"] < 1.2:
            errs.append(f'{sc["id"]}: shorter than 1.2 s')
        prev = sc["end"]
    if abs(prev - DUR) > 0.05:
        errs.append(f"last scene ends at {prev}, duration is {DUR}")
    for sc in SCENES:
        for key in ("img",):
            if key in sc and not os.path.exists(f"{OUT}/assets/{sc[key]}"):
                errs.append(f'{sc["id"]}: missing asset {sc[key]}')
        if sc["type"] == "compare":
            for k in ("top", "bottom"):
                if not os.path.exists(f'{OUT}/assets/{sc[k]["src"]}'):
                    errs.append(f'{sc["id"]}: missing asset {sc[k]["src"]}')
    if errs:
        sys.exit("spec errors:\n  " + "\n  ".join(errs))


if __name__ == "__main__":
    validate()
    os.makedirs(f"{OUT}/compositions", exist_ok=True)
    for sc in SCENES:
        base = len(SFX)
        write_scene(sc)
        for k in range(base, len(SFX)):
            n, at, v, du = SFX[k]
            SFX[k] = (n, round(at + sc["start"], 2), v, du)
    write_captions()
    write_root()
    print(f"built {len(SCENES)} scenes, {len(caption_groups())} caption groups, {len(SFX)} sfx")
