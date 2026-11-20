#!/usr/bin/env python3
"""Screenshot-led reel builder: <job>/deck.json -> <job>/edit (HyperFrames), drawn in one of 4 templates by deck.py.

usage: deck_reel.py <job_dir> [--check]
--check validates the spec and builds, printing every problem; without problems it prints "built ...".

Reads   <job>/deck.json, <job>/words.json ([[text, start, end], ...]), <job>/edit/work/duration.txt
        <job>/edit/assets/: face_cutout.webm, voice.wav, music.wav, sfx/, img/<name>.jpg + img/<name>.json (from grab.mjs)

deck.json:
{
  "template": "paper | clean | notebook | lime",
  "reason": "one short line: why this template fits these screenshots",
  "keywords": ["google", "timesfm"],          # caption words that get the highlight
  "scenes": [ {"kind": ..., "at": "<spoken words that start the scene>", ...}, ... ]
}
Every scene starts on the first word of `at` (copy 1-3 consecutive words exactly from words.json; "n": 1 picks the
2nd time they are spoken). The first scene starts at 0 and has no `at`. A scene ends where the next one starts.

Scene kinds
  card      a real page screenshot in a browser card, framed automatically around its marks
            img: "tf_repo" (a grab.mjs capture), url: "github.com/google-research/timesfm"
            face: "card" (presenter under the card, default) | "hidden" (bigger card over a backdrop)
            title: {"kicker": "IT'S CALLED", "text": "TimesFM", "em": "TimesFM"}   optional; em = accent words of text
            marks: [{"find": "<exact text on the page>", "at": "<spoken words>", "style": "marker | circle"}]
                   find must be one of the phrases grab.mjs --find located (img json "found"); marker = highlight
                   a line of text, circle = ring a button, number, logo or heading (glow box / circle / bracket per template)
            focus: "<found text>"        frame on this without marking it (when there are no marks)
            zoom: "wide | normal | close"   how much of the page width shows (1180 / 900 / 620 css px); default shows the whole page width (nothing cut at the sides). Use zoom only when asked.
            sticker: {"text": "35K GitHub stars", "at": "..."}   stat: {"num": 100, "suffix": "B+", "label": "data points", "at": "..."}
            chip: "1/4"        section: true (a new topic: transition + bigger sound)
  face      the presenter full screen with a slow push-in
            stickers: [{"text": "weeks of training", "at": "weeks"}] (0-3)   stat: {...} as above
            a sticker with "logo": "youtube" is drawn as a big app-icon tile with that brand's real logo instead of a text pill
  logos     real brand logos in tiles under a title, presenter under them, each popping in as it is spoken
            items: [{"logo": "youtube", "label": "YouTube", "at": "YouTube"}, ...] (2-6)   title, section as above
  image     a real image (from media.py) filling a card, with a slow push-in. img: "<name>", face: card | hidden, title, section, sticker, stat
  broll     a free stock video clip (from media.py broll-get) playing in a card, presenter under it, for a moment that has no page or
            image to show (an example, a story, a feeling). video: "<name>", title, section, sticker, stat as above
  terminal  typed terminal, presenter under it. window: "terminal — timesfm", lines: ["> forecast sales.csv", "✓ forecast ready"]
            (a "> " line is typed as a command, others print), chip, section, title card as above
  cta       last scene, at "Comment <WORD>": word: "GOOGLE"
"""
import difflib, glob, json, math, os, re, subprocess, sys

import hashlib


def pick_layout(job):
    """1 = blurred studio (most reels), 2 = template background (about 1 in 3). deck.json "layout": 1|2 overrides.
    Fixed per job, so --check and the render always agree."""
    try:
        forced = json.load(open(f"{job}/deck.json")).get("layout")
    except Exception:
        forced = None
    if forced in (1, 2):
        return forced
    return 2 if int(hashlib.md5(os.path.basename(job.rstrip("/")).encode()).hexdigest(), 16) % 3 == 0 else 1


LAYOUT = pick_layout(os.path.abspath(sys.argv[1])) if len(sys.argv) > 1 else 1
os.environ["LAYOUT"] = str(LAYOUT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deck import Deck, STYLES

TEMPLATES = ("paper", "clean", "notebook", "lime")
SND = {"cinema": dict(enter="whoosh-cinematic", section="impact-bass-1", mark="ping", stat="riser", type="typing"),
       "paper": dict(enter="whoosh-short", section="pop", mark="click-soft", stat="sparkle", type="key-press"),
       "neon": dict(enter="glitch-1", section="glitch-2", mark="glitch-3", stat="chime", type="typing")}
ZOOM = {"wide": 1180, "normal": 900, "close": 620}
TOP, CARD_BOTTOM, HIDDEN_BOTTOM, CARD_X, CARD_W = 200, 790, 1010, 70, 940
ICONS = f"{os.path.dirname(os.path.abspath(__file__))}/logos/node_modules/@iconify-json"
LOGO_ALIAS = {"chatgpt": "openai", "x": "x", "twitterx": "x", "gemini": "googlegemini", "claudecode": "claude", "vscode": "visual-studio-code"}


class SpecError(Exception):
    pass


def main():
    job = os.path.abspath(sys.argv[1])
    errors = []
    spec = json.load(open(f"{job}/deck.json"))
    words = json.load(open(f"{job}/words.json"))
    D = float(open(f"{job}/edit/work/duration.txt").read())
    tpl = spec.get("template")
    if tpl not in TEMPLATES:
        raise SystemExit(f"spec error: template must be one of {TEMPLATES}, got {tpl!r}")
    out = f"{job}/edit"
    for f in glob.glob(f"{out}/compositions/*.html"):
        os.remove(f)
    blur = f"{out}/assets/face_blur.mp4"
    if LAYOUT == 1 and not os.path.exists(blur):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{out}/assets/face.mp4", "-an", "-vf",
                        "scale=360:-2,gblur=sigma=14,eq=brightness=-0.12:saturation=1.1,scale=1080:1920",
                        "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-g", "30", "-pix_fmt", "yuv420p", blur], check=True)
    open(f"{job}/layout.txt", "w").write(str(LAYOUT))
    d = Deck(out, D, tpl, words)
    b = Builder(d, spec, out, D, errors)
    b.build()
    if errors:
        print("spec errors:\n- " + "\n- ".join(errors))
        sys.exit(1)
    print("built", tpl, f"layout {LAYOUT}", len(d.scenes), "scenes", f"{D}s")


class Builder:
    def __init__(self, d, spec, out, D, errors):
        self.d, self.spec, self.out, self.D, self.err = d, spec, out, D, errors
        self.snd = SND[d.fam]
        self.tilt_on = d.fam == "paper" and d.s["card"] == "polaroid"

    # ------------------------------------------------------------ helpers
    def t(self, phrase, n=0, where=""):
        try:
            return self.d.T(phrase, n)
        except KeyError:
            first = re.sub(r"[^a-z0-9]", "", phrase.split()[0].lower()) if phrase.split() else ""
            near = sorted({w[0] for w in self.d.words if first and re.sub(r"[^a-z0-9]", "", w[0].lower()).startswith(first[:3])})[:8]
            self.err.append(f"{where}: {phrase!r} is not spoken in words.json (similar words: {near})")
            return None

    def tilt(self, n):
        return (-2.2, 1.8, -1.4, 2.4)[n % 4] if self.tilt_on else 0

    def page(self, img, where):
        j = f"{self.out}/assets/img/{img}.json"
        if not os.path.exists(j) or not os.path.exists(f"{self.out}/assets/img/{img}.jpg"):
            self.err.append(f"{where}: no capture named {img!r} (run grab.mjs first)")
            return None
        return json.load(open(j))

    def logo(self, name):
        """Write the brand's real logo to assets/logos and return its file name. Colour set first, one-colour set second."""
        n = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
        n = LOGO_ALIAS.get(n.replace("-", ""), n)
        if not hasattr(self, "icon_sets"):
            self.icon_sets = [json.load(open(f"{ICONS}/{p}/icons.json")) for p in ("logos", "simple-icons")]
        for pack in self.icon_sets:
            for key in (f"{n}-icon", n):
                ic = pack["icons"].get(key)
                if ic:
                    w, h = ic.get("width", pack.get("width", 24)), ic.get("height", pack.get("height", 24))
                    os.makedirs(f"{self.out}/assets/logos", exist_ok=True)
                    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{ic["body"].replace("currentColor", "#111111")}</svg>'
                    open(f"{self.out}/assets/logos/{n}.svg", "w").write(svg)
                    return f"{n}.svg"
        near = difflib.get_close_matches(n, [k for p in self.icon_sets for k in p["icons"]], 6)
        raise SpecError(f"no logo named {name!r} (close: {near})")

    def backdrop(self, img):
        """Blurred copy of the page for full-screen backdrops (templates without a colour block)."""
        src, dst = f"{self.out}/assets/img/{img}.jpg", f"{self.out}/assets/img/bg_{img}.jpg"
        if not os.path.exists(dst):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                            "crop=iw:'min(ih,iw*1.5)':0:0,scale=540:-2,gblur=sigma=14", "-q:v", "4", dst], check=True)
        return f"bg_{img}.jpg"

    def title_h(self, title):
        """Top of the area under a title (kicker line + wrapped heading)."""
        s = self.d.s
        hs = s["head_size"]
        per_line = int(960 / (hs * .56))
        lines = max(1, -(-len(title["text"]) // per_line))
        return TOP - 50 + (56 if title.get("kicker") else 0) + int(lines * hs * 1.04) + 80

    # ------------------------------------------------------------ build
    def build(self):
        d, scenes = self.d, self.spec.get("scenes", [])
        if not 6 <= len(scenes) <= 14:
            self.err.append(f"use 6-14 scenes, got {len(scenes)}")
        if not scenes or scenes[-1].get("kind") != "cta":
            self.err.append("the last scene must be kind cta")
        starts = []
        for i, sc in enumerate(scenes):
            if i == 0:
                starts.append(0.0)
                continue
            st = self.t(sc.get("at", ""), sc.get("n", 0), f"scene {i + 1} at")
            starts.append(st)
        if self.err:
            return
        for i in range(1, len(starts)):
            if starts[i] - starts[i - 1] < 1.2:
                self.err.append(f"scene {i} lasts {starts[i] - starts[i - 1]:.2f}s (min 1.2s): merge it or move scene {i + 1}'s at")
        if self.D - starts[-1] < 1.2:
            self.err.append("the cta scene is shorter than 1.2s")
        if self.err:
            return
        ends = starts[1:] + [self.D]
        cards = 0
        for i, sc in enumerate(scenes):
            sid, s, e = f"s{i + 1}", starts[i], ends[i]
            kind = sc.get("kind")
            where = f"scene {i + 1} ({kind})"
            try:
                if kind == "card":
                    self.card(sid, s, e, sc, i == 0 or sc.get("section"), cards, where)
                    cards += 1
                elif kind == "face":
                    self.face(sid, s, e, sc, where)
                elif kind == "logos":
                    self.logos(sid, s, e, sc, i == 0 or sc.get("section"), where)
                elif kind == "image":
                    self.image(sid, s, e, sc, i == 0 or sc.get("section"), cards, where)
                    cards += 1
                elif kind == "broll":
                    self.broll(sid, s, e, sc, i == 0 or sc.get("section"), cards, where)
                    cards += 1
                elif kind == "terminal":
                    self.terminal(sid, s, e, sc, i == 0 or sc.get("section"), where)
                elif kind == "cta":
                    if i != len(scenes) - 1:
                        self.err.append(f"{where}: cta must be the last scene")
                    word = sc.get("word", "").strip().upper() or "INFO"
                    d.scene(sid, s, e, "full", *d.cta(sid, word, .5), section=True)
                    d.fx(self.snd["section"], s, .35, 1)
                    d.fx("sparkle", s + .3, .3, 1.2)
                else:
                    self.err.append(f"{where}: unknown kind")
            except SpecError as x:
                self.err.append(f"{where}: {x}")
        if cards < len(scenes) * .35:
            self.err.append(f"only {cards} card, image and broll scenes of {len(scenes)}: show real pages, images or b-roll in at least 35% of the scenes")
        if self.err:
            return
        kw = {re.sub(r"[^a-z0-9]", "", k.lower()) for k in self.spec.get("keywords", [])}
        d.captions(kw, skip=[(starts[-1], self.D)])
        d.write_root("music.wav", .12)

    def at_or(self, x, default, where):
        """Time of an item's spoken `at`, or scene start + default."""
        if x and x.get("at"):
            v = self.t(x["at"], x.get("n", 0), where)
            if v is None:
                raise SpecError(f"{x['at']!r} not spoken")
            return v
        return default

    def extras(self, sid, s, e, sc, where, stat_xy, sticker_xy):
        """Optional stat + sticker + chip on a scene. Returns (body, js)."""
        d, body, js = self.d, "", []
        if sc.get("stat"):
            st = sc["stat"]
            t = self.at_or(st, s + .4, where + " stat")
            if not s <= t < e:
                raise SpecError("stat at is outside the scene")
            w = 360 if d.s["stat"] == "sticker" else 420
            b, j = d.stat(f"{sid}-stat", st["num"], st.get("suffix", ""), st.get("label", ""), stat_xy[0], stat_xy[1], t - s, 0, w)
            body += b
            js += j
            d.fx(self.snd["stat"], t, .2, 1)
        if sc.get("sticker"):
            st = sc["sticker"]
            t = self.at_or(st, s + .6, where + " sticker")
            if not s <= t < e:
                raise SpecError("sticker at is outside the scene")
            b, j = d.sticker(f"{sid}-st", st["text"], sticker_xy[0], sticker_xy[1], t - s, sticker_xy[2])
            body += b
            js += j
            d.fx("pop", t, .28, .5)
        return body, js

    def head(self, sid, sc, where):
        """Title over the card. Returns (body, js, y under the title)."""
        title = sc.get("title")
        if isinstance(title, str):
            raise SpecError("title must be {kicker, text, em} (a terminal's window name goes in window)")
        if not title:
            return "", [], TOP
        if len(title.get("text", "").split()) > 7:
            raise SpecError("title text over 7 words")
        b, j = self.d.title(sid, title.get("kicker", ""), title["text"], TOP - 50, 0, em=title.get("em"))
        return b, j, self.title_h(title)

    def card(self, sid, s, e, sc, section, n, where):
        d = self.d
        pg = self.page(sc.get("img", ""), where)
        if pg is None:
            raise SpecError("missing capture")
        face = sc.get("face", "card")
        if face not in ("card", "hidden"):
            raise SpecError("card face must be card or hidden")
        tb, tj, y = self.head(sid, sc, where)
        bottom = CARD_BOTTOM if face == "card" else HIDDEN_BOTTOM
        h = bottom - y
        if h < 300:
            raise SpecError(f"title too long, card only {h}px tall: shorten the title or use face hidden")
        x, w = (CARD_X, CARD_W) if face == "card" else (50, 980)
        found = pg.get("found", {})

        # region to frame: the marks, else the focus, else the top of the page
        boxes, marks = [], []
        for m in sc.get("marks", []):
            box = found.get(m.get("find", ""))
            if not box:
                raise SpecError(f"mark {m.get('find')!r} was not located on {sc['img']} (found: {list(found)[:12]})")
            t = self.at_or(m, s + .5, where + " mark")
            if not s <= t < e - .3:
                raise SpecError(f"mark {m['find']!r} is spoken outside the scene")
            marks.append((m, box, t))
            boxes.append(box)
        if not boxes and sc.get("focus"):
            if sc["focus"] not in found:
                raise SpecError(f"focus {sc['focus']!r} was not located on {sc['img']}")
            boxes.append(found[sc["focus"]])
        vw = ZOOM.get(sc.get("zoom"), 0)
        if not vw:
            # default: the page's whole content width, so buttons, logos and text are never cut at the sides
            xs = [l for l in pg.get("lines", []) if l["w"] > 0]
            cx0 = max(0, min([l["x"] for l in xs] + [b["x"] for b in boxes], default=0) - 24)
            cx1 = min(1280, max([l["x"] + l["w"] for l in xs] + [b["x"] + b["w"] for b in boxes], default=1280) + 24)
            vx, vw = cx0, max(620, cx1 - cx0)
            if vx + vw > 1280:
                vx = max(0, 1280 - vw)
        if boxes and sc.get("zoom") in ZOOM:
            x0 = min(b["x"] for b in boxes)
            x1 = max(b["x"] + b["w"] for b in boxes)
            blocks = [b["block"] for b in boxes if b.get("block") and b["block"]["w"] < 1240]
            if blocks:  # frame the text column the marks sit in, from its left edge, so no line is cut at the start
                bx0 = min(b["x"] for b in blocks)
                bx1 = max(b["x"] + b["w"] for b in blocks)
                if not sc.get("zoom"):
                    vw = max(620, min(1000, bx1 - bx0 + 60))
                vw = min(1280, max(vw, x1 - x0 + 80))
                # start at the left edge of the text column around the marks (wide text blocks near them)
                y0, y1 = min(b["y"] for b in boxes), max(b["y"] + b["h"] for b in boxes)
                col = [l["x"] for l in pg.get("lines", []) if l["w"] > 220 and l["x"] <= x0 and y0 - 300 < l["y"] < y1 + 300]
                left = min([bx0, x0] + [c for c in col if x1 + 30 - c <= vw])
                vx = max(0, min(1280 - vw, left - 30))
                if x1 + 30 > vx + vw:
                    vx = min(1280 - vw, x1 + 30 - vw)
            else:
                vw = min(1280, max(vw, x1 - x0 + 80))
                vx = max(0, min(1280 - vw, (x0 + x1) / 2 - vw / 2))
        elif sc.get("zoom") in ZOOM:
            vx = max(0, (1280 - vw) / 2 - 140) if vw < 1280 else 0
        sc_ = w / vw
        vis = (h - 52) / sc_  # page css px visible in the card
        page_h = pg["height"]

        def pan_for(b):
            return max(0, min(page_h - vis, b["y"] + b["h"] / 2 - vis * .42))

        inner, js = "", []
        for k, (m, box, t) in enumerate(marks):
            if m.get("style", "marker") == "marker":  # one sweep per text line, each starting as the last ends
                for li, r in enumerate(box.get("lines") or [box]):
                    b, j = d.marker(f"{sid}-m{k}l{li}", (r["x"] - 4 - vx) * sc_, 52 + (r["y"] - 3) * sc_, (r["w"] + 8) * sc_,
                                    (r["h"] + 6) * sc_, t - s + li * .4)
                    inner += b
                    js += j
            else:
                b, j = d.mark(f"{sid}-m{k}", (box["x"] - 8 - vx) * sc_, 52 + (box["y"] - 6) * sc_, (box["w"] + 16) * sc_,
                              (box["h"] + 12) * sc_, t - s)
                inner += b
                js += j
            d.fx(self.snd["mark"], t, .22, .5)
        body = d.card(sid, x, y, w, h, sc.get("url", ""), f"{sc['img']}.jpg", inner, (vx, vx + vw))
        tape = f",#{sid}-tape" if d.s["card"] == "polaroid" else ""
        js.insert(0, d.enter(f"#{sid}-card{tape}", .02, self.tilt(n)))
        # camera: start on the first mark, glide to each later mark just before it is spoken, else drift down slowly
        targets = [pan_for(b) for b in boxes] or [0]
        p0 = targets[0]
        js.append(f'tl.set("#{sid}-pan",{{y:{-p0 * sc_:.1f},x:0,scale:1,transformOrigin:"0 0"}},0);')
        for m, box, t in marks:  # whole page first, then the camera pushes in on the line as it is spoken
            bw = box["w"] * sc_
            zoom = max(1.3, min(2.1, (w - 90) / max(bw, 1)))
            px, py = (box["x"] + box["w"] / 2 - vx) * sc_, 52 + (box["y"] + box["h"] / 2) * sc_
            cx = max(w - zoom * w, min(0, w / 2 - zoom * px))
            cy = max(h - zoom * (52 + page_h * sc_), min(0, (h + 52) / 2 - zoom * py))
            js.append(f'tl.to("#{sid}-pan",{{x:{cx:.1f},y:{cy:.1f},scale:{zoom:.2f},duration:.55,ease:"power2.inOut"}},{max(.15, t - s - .2):.2f});')
        if not marks:
            drift = min(40, max(0, page_h - vis - p0))
            js.append(f'tl.to("#{sid}-pan",{{y:{-(p0 + drift) * sc_:.1f},duration:{e - s:.2f},ease:"none"}},0);')
        if face == "card":
            eb, ej = self.extras(sid, s, e, sc, where, (600, y + h - 230), (560, y - 34, 5))
        else:
            eb, ej = self.extras(sid, s, e, sc, where, (600, bottom - 200), (90, bottom - 40, -4))
        if sc.get("chip"):
            cb, cj = d.chip(f"{sid}-chip", sc["chip"], x + w - 170, y - 28, .35)
            eb += cb
            ej += cj
        js += tj + ej
        js.append(d.leave(f"#{sid}-wrap", e - s - .26))
        alt = None
        if face == "hidden":
            alt = self.backdrop(sc["img"]) if d.fam != "paper" else sc["img"] + ".jpg"
        d.scene(sid, s, e, face, tb + body + eb, js, alt=alt, section=bool(section))
        d.fx(self.snd["enter"], s, .28, .8)
        if section:
            d.fx(self.snd["section"], s, .35, 1.2)

    def face(self, sid, s, e, sc, where):
        d, body, js = self.d, "", []
        # everything sits in the free band above the head (y < 640): logos in a row, text under them; a stat keeps the right side
        has_stat, sts_all = bool(sc.get("stat")), sc.get("stickers", [])
        n_logo = sum(1 for st in sts_all if st.get("logo"))
        tile_spots = ((60, 170, -5), (390, 110, 3), (720, 170, 5))[:2 if has_stat else 3]
        if len(sts_all) and n_logo > len(tile_spots):
            raise SpecError("at most 2 logos next to a stat")
        if has_stat:
            text_spots = ((40, 110, -4), (40, 200, 3), (40, 290, -3))
        elif n_logo:
            text_spots = ((60, 450, -4), (540, 520, 4), (280, 560, -2))
        else:
            text_spots = ((40, 90, -5), (540, 90, 4), (40, 190, -3))
        sts = sc.get("stickers", [])
        if len(sts) > 3:
            raise SpecError("at most 3 stickers")
        tiles = texts = 0
        for k, st in enumerate(sts):
            t = self.at_or(st, s + .5 + k * .6, where + " sticker")
            if not s <= t < e:
                raise SpecError(f"sticker {st.get('text')!r} is spoken outside the scene")
            if st.get("logo"):
                x, y, rot = tile_spots[tiles]
                tiles += 1
                b, j = d.logo_tile(f"{sid}-st{k}", x, y, 300, 300, self.logo(st["logo"]), st.get("text", ""), t - s, rot)
            else:
                x, y, rot = text_spots[texts]
                texts += 1
                b, j = d.sticker(f"{sid}-st{k}", st["text"], x, y, t - s, rot)
            body += b
            js += j
            d.fx("pop", t, .28, .5)
        if sc.get("stat"):
            b, j = self.extras(sid, s, e, {"stat": sc["stat"]}, where, (720, 30), (0, 0, 0))
            body += b
            js += j
        d.scene(sid, s, e, "full", body, js + [d.leave(f"#{sid}-wrap", e - s - .2)])

    def logos(self, sid, s, e, sc, section, where):
        d = self.d
        items = sc.get("items", [])
        if not 2 <= len(items) <= 6:
            raise SpecError("logos needs 2-6 items")
        tb, tj, y = self.head(sid, sc, where)
        cols = {2: 2, 3: 3, 4: 2, 5: 3, 6: 3}[len(items)]
        rows, gap, h = math.ceil(len(items) / cols), 26, CARD_BOTTOM - y
        tw = (CARD_W - gap * (cols - 1)) / cols
        th = min((h - gap * (rows - 1)) / rows, tw)
        if th < 150:
            raise SpecError("title too long for this many logos")
        top = y + (h - (th * rows + gap * (rows - 1))) / 2
        body, js = tb, list(tj)
        for k, it in enumerate(items):
            t = self.at_or(it, s + .15 + k * .25, where + " logo")
            if not s <= t < e:
                raise SpecError(f"logo {it.get('logo')!r} is spoken outside the scene")
            r, c = divmod(k, cols)
            pad = (CARD_W - (tw * (len(items) - r * cols) + gap * (len(items) - r * cols - 1))) / 2 if r == rows - 1 else 0
            b, j = d.logo_tile(f"{sid}-l{k}", CARD_X + pad + c * (tw + gap), top + r * (th + gap), tw, th,
                               self.logo(it.get("logo", "")), it.get("label", ""), t - s, 0, ghost=True)
            body += b
            js += j
            d.fx("pop", t, .28, .5)
        d.scene(sid, s, e, "card", body, js + [d.leave(f"#{sid}-wrap", e - s - .26)], section=bool(section))
        d.fx(self.snd["enter"], s, .22, .8)
        if section:
            d.fx(self.snd["section"], s, .35, 1.2)

    def image(self, sid, s, e, sc, section, n, where):
        d = self.d
        if not os.path.exists(f"{self.out}/assets/img/{sc.get('img', '')}.jpg"):
            raise SpecError(f"no image named {sc.get('img')!r} (run media.py first)")
        face = sc.get("face", "card")
        if face not in ("card", "hidden"):
            raise SpecError("image face must be card or hidden")
        tb, tj, y = self.head(sid, sc, where)
        bottom = CARD_BOTTOM if face == "card" else HIDDEN_BOTTOM
        h = bottom - y
        if h < 300:
            raise SpecError(f"title too long, image only {h}px tall")
        x, w = (CARD_X, CARD_W) if face == "card" else (50, 980)
        body = d.photo(sid, x, y, w, h, f"{sc['img']}.jpg")
        js = [d.enter(f"#{sid}-card", .02, self.tilt(n)),
              f'tl.fromTo("#{sid}-img",{{scale:1}},{{scale:1.09,duration:{e - s:.2f},ease:"none"}},0);'] + tj
        eb, ej = self.extras(sid, s, e, sc, where, (600, y + h - 230), (560, y - 34, 5))
        alt = None
        if face == "hidden":
            alt = self.backdrop(sc["img"]) if d.fam != "paper" else sc["img"] + ".jpg"
        d.scene(sid, s, e, face, tb + body + eb, js + ej + [d.leave(f"#{sid}-wrap", e - s - .26)], alt=alt, section=bool(section))
        d.fx(self.snd["enter"], s, .28, .8)
        if section:
            d.fx(self.snd["section"], s, .35, 1.2)

    def broll(self, sid, s, e, sc, section, n, where):
        d = self.d
        if not os.path.exists(f"{self.out}/assets/broll/{sc.get('video', '')}.mp4"):
            raise SpecError(f"no b-roll named {sc.get('video')!r} (run media.py broll-get first)")
        tb, tj, y = self.head(sid, sc, where)
        h = CARD_BOTTOM - y
        if h < 300:
            raise SpecError(f"title too long, b-roll only {h}px tall")
        body = d.clip_card(sid, CARD_X, y, CARD_W, h, f"{sc['video']}.mp4", e - s)
        js = [d.enter(f"#{sid}-card", .02, self.tilt(n)),
              f'tl.fromTo("#{sid}-img",{{scale:1}},{{scale:1.06,duration:{e - s:.2f},ease:"none"}},0);'] + tj
        eb, ej = self.extras(sid, s, e, sc, where, (600, y + h - 230), (560, y - 34, 5))
        d.scene(sid, s, e, "card", tb + body + eb, js + ej + [d.leave(f"#{sid}-wrap", e - s - .26)], section=bool(section))
        d.fx(self.snd["enter"], s, .28, .8)
        if section:
            d.fx(self.snd["section"], s, .35, 1.2)

    def terminal(self, sid, s, e, sc, section, where):
        d = self.d
        lines = sc.get("lines", [])
        if not 1 <= len(lines) <= 6:
            raise SpecError("terminal needs 1-6 lines")
        if any(len(l) > 40 for l in lines):
            raise SpecError("terminal lines must be under 40 characters")
        tb, tj, y = self.head(sid, sc, where)
        h = min(460, CARD_BOTTOM - y)
        if h < 260:
            raise SpecError("title too long for a terminal")
        term, tt = d.terminal(f"{sid}-term", CARD_X, y, CARD_W, h, sc.get("window", "terminal"),
                              [(l, .2 if k else .15) for k, l in enumerate(lines)], .15, cps=30)
        js = tj + [d.enter(f"#{sid}-term", .02, self.tilt(0))] + tt
        body = tb + term
        if sc.get("chip"):
            b, j = d.chip(f"{sid}-chip", sc["chip"], 700, y - 28, .6)
            body += b
            js += j
        eb, ej = self.extras(sid, s, e, sc, where, (600, y + h - 200), (560, y - 34, 5))
        d.scene(sid, s, e, "card", body + eb, js + ej + [d.leave(f"#{sid}-wrap", e - s - .26)], section=bool(section))
        d.fx(self.snd["enter"], s, .25, .8)
        d.fx(self.snd["type"], s + .2, .25, 1.4)
        if section:
            d.fx(self.snd["section"], s, .35, 1.2)


if __name__ == "__main__":
    main()
