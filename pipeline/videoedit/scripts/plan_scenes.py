"""Draft a scene plan from the cut transcript. Claude then reads it, fixes it and fills the blanks.

Usage: python plan_scenes.py <work_dir> <draft_plan.json> [watermark]
Reads <work_dir>/captions.json, cut_map.json, cut.mp4 (duration). Finds:
  - list items: ordinal words (pehle, second/doosra, teesra, chautha, paanchva, chhatha, agla, aakhri ...)
    with the first % and ₹ amount after them -> badge + photo slot (img left empty, query suggested)
  - hook: an amount / number in the first 8 s -> premium card
  - CTA: "comment" / "subscribe" / "batao" near the end -> lower third
  - end card on the last 2.6 s
  - face-only gaps >= 3 s -> "sticker_slots" with what is said there (Claude writes the sticker text)
Everything uncertain is marked "TODO" so it cannot slip into a render unnoticed.
"""
import json
import re
import subprocess
import sys

work, out = sys.argv[1], sys.argv[2]
mark = sys.argv[3] if len(sys.argv) > 3 else ""
chunks = json.load(open(f"{work}/captions.json", encoding="utf-8"))
words = [w for c in chunks for w in c["words"]]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            f"{work}/cut.mp4"], capture_output=True, text=True).stdout.strip())

ORD = {"pehle": 1, "pehla": 1, "second": 2, "doosra": 2, "dusra": 2, "teesra": 3, "tisra": 3, "chautha": 4,
       "paanchva": 5, "panchva": 5, "fifth": 5, "chhatha": 6, "chhata": 6, "saatva": 7, "aathva": 8, "nauva": 9,
       "agla": None, "next": None, "aakhri": "last", "last": "last"}
norm = lambda t: re.sub(r"[^\w₹%,]", "", t.lower())
amount = lambda t: re.fullmatch(r"₹?[\d,]+", t) and "," in t
pct = lambda t: t.endswith("%")
to_int = lambda t: int(re.sub(r"[^\d]", "", t))

# ---- list items
items, n = [], 0
for i, w in enumerate(words):
    key = norm(w["t"])
    if key not in ORD or (key == "pehle" and (i == 0 or norm(words[i - 1]["t"]) != "sabse")):
        continue
    if items and w["s"] - items[-1]["start"] < 3:      # "agla agla", "sabse pehle 22%"
        continue
    n = n + 1 if ORD[key] in (None, "last") else ORD[key]
    items.append({"n": n, "start": round(words[i - 1]["s"] if key == "pehle" else w["s"], 2), "idx": i})
for k, it in enumerate(items):
    stop = items[k + 1]["idx"] if k + 1 < len(items) else min(len(words), it["idx"] + 40)
    span = words[it["idx"]:stop]
    p = next((w for w in span if pct(w["t"])), None)
    a = next((w for w in span if amount(w["t"])), None)
    it["pct"] = p["t"] if p else ""
    it["amount"] = a["t"] if a else ""
    it["amount_at"] = round(a["s"], 2) if a else None
    after = [w["t"] for w in span if a and w["s"] > a["e"]][:10]
    it["said"] = " ".join(w["t"] for w in span)[:160]
    it["query_hint"] = " ".join(after)
    # the last item has no next ordinal: stop it at the first pause after its amount
    if k + 1 == len(items) and a:
        rest = [w for w in span if w["s"] > a["e"]]
        stop_w = next((w for x, w in zip(rest, rest[1:]) if w["s"] - x["e"] > 0.45), None)
        span = [w for w in span if w["s"] < (stop_w["s"] if stop_w else a["e"] + 5.5)]
    it["end"] = round(min(span[-1]["e"] + 0.05, (a["e"] + 3.5) if a else span[-1]["e"] + 0.05), 2)

scenes, slots = [], []
taken = []


def add(sc, full_screen=True):
    scenes.append(sc)
    taken.append((sc["start"], sc["end"]))


# ---- hook
first = next((w for w in words if w["s"] < 8 and (amount(w["t"]) or pct(w["t"]))), None)
if first:
    big = first["t"] if first["t"].startswith("₹") or pct(first["t"]) else "₹" + first["t"]
    add({"type": "card", "start": round(max(0.3, first["s"] - 0.3), 2), "end": round(first["e"] + 1.6, 2),
         "top": "TODO short kicker (2-5 words, CAPS)", "big": big, "bottom": "TODO one-line question",
         "roll_to": to_int(first["t"]) if amount(first["t"]) else None})

# ---- items
for it in items:
    if it["amount_at"] is not None:
        b_end = it["amount_at"] - 0.2
        if b_end - it["start"] > 0.8:
            add({"type": "badge", "start": round(it["start"] + 0.05, 2), "end": round(b_end, 2),
                 "n": it["n"], "pct": it["pct"]})
        a = it["amount"] if it["amount"].startswith("₹") else "₹" + it["amount"]
        add({"type": "photo", "start": round(it["amount_at"] - 0.15, 2),
             "end": round(min(it["amount_at"] + 3.4, it["end"]), 2), "img": "TODO.jpg", "pos": "50% 50%",
             "tag": f"#{it['n']} · {it['pct']} · TODO title".replace(" ·  ·", " ·"), "big": a,
             "line": "TODO detail (3-6 words)", "roll_to": to_int(it["amount"]),
             "query": "TODO Commons search", "said": it["said"]})
    else:
        add({"type": "badge", "start": round(it["start"] + 0.05, 2), "end": round(min(it["start"] + 2.5, it["end"]), 2),
             "n": it["n"], "pct": it["pct"]})
if len(items) >= 3:
    scenes.append({"type": "progress", "start": items[0]["start"], "end": items[-1]["end"],
                   "items": [{"at": it["start"], "label": f"{it['n']}/{len(items)} · TODO"} for it in items]})

# ---- CTA + end
cta = next((w for w in words if w["s"] > dur * 0.6 and norm(w["t"]) in ("comment", "subscribe")), None)
if cta:
    add({"type": "cta", "start": round(cta["s"] - 0.3, 2), "end": round(min(cta["s"] + 4.7, dur - 2.8), 2),
         "kicker": "Comment karke batao", "line": "TODO question for viewers"})
add({"type": "end", "start": round(dur - 2.6, 2), "end": round(dur, 2), "thumbs": []})

# ---- face-only gaps for stickers
taken.sort()
t = 0.0
for a, b in taken + [(dur, dur)]:
    if a - t >= 3.0:
        said = " ".join(w["t"] for w in words if t <= w["s"] < a)
        slots.append({"start": round(t + 0.3, 2), "end": round(a - 0.2, 2), "said": said[:200]})
    t = max(t, b)

plan = {"cut": f"{work}/cut.mp4", "cut_map": f"{work}/cut_map.json", "captions": f"{work}/captions.json",
        "images": f"{work}/images", "duration": round(dur, 2), "captions_mode": "full", "watermark": mark,
        "scenes": sorted(scenes, key=lambda s: s["start"]), "sticker_slots": slots,
        "items_found": [{k: v for k, v in it.items() if k != "idx"} for it in items]}
json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"duration {dur:.1f}s | {len(items)} list items | {len(scenes)} scenes | {len(slots)} sticker slots")
for it in items:
    print(f"  #{it['n']:<2} {it['start']:7.2f}  {it['pct']:>5} {it['amount']:>11}  {it['said'][:70]}")
for s in slots:
    print(f"  slot {s['start']:7.2f}-{s['end']:7.2f}  {s['said'][:80]}")
