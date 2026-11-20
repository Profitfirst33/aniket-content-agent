"""Find retakes in a raw talking-head transcript and write keep.json (the last full take of every line).

Usage: python find_retakes.py <transcript.json> <keep.json>

Rules
- A "restart": a run of words that starts a phrase (after a pause, or at the very start) is spoken again,
  at a later phrase start, within 45 s, matching >= 3 words in a row (fuzzy, so मैंना ~ मैंने).
  Everything from the earlier start up to the LAST such restart is dropped.
- A "corrected number": two amounts back to back ("1,82,000, 1,88,792") -> the first one is dropped.
Prints every drop so it can be shown to the user before cutting.
"""
import difflib
import json
import re
import sys

WINDOW = 45.0
PHRASE_GAP = 0.40
MIN_MATCH = 3

words = [w for s in json.load(open(sys.argv[1], encoding="utf-8"))["segments"] for w in s["words"]]
norm = [re.sub(r"[^\w]", "", w["w"].lower()) for w in words]
n = len(words)


def same(a, b):
    if not a or not b:
        return a == b
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def phrase_start(i, loose=False):
    """A real pause (or the first word). loose=True also accepts a word right after a comma or full stop."""
    if i == 0 or words[i]["s"] - words[i - 1]["e"] >= PHRASE_GAP:
        return True
    return loose and words[i - 1]["w"].endswith((",", ".", "?"))


def match_len(i, j):
    k = 0
    while j + k < n and i + k < j and same(norm[i + k], norm[j + k]):
        k += 1
    return k


drops = []  # (start_sec, end_sec, why)
i = 0
while i < n:
    if not phrase_start(i):
        i += 1
        continue
    best = None
    j = i + 1
    while j < n and words[j]["s"] - words[i]["s"] <= WINDOW:
        if phrase_start(j, loose=True) and match_len(i, j) >= MIN_MATCH:
            best = j
        j += 1
    if best is not None:
        drops.append((words[i]["s"] - 0.05, words[best]["s"] - 0.08,
                      "retake: " + " ".join(w["w"] for w in words[i:min(best, i + 8)]) + " …"))
        i = best
    else:
        i += 1

# corrected numbers: digit groups glued together, two amounts with nothing in between
amounts, cur = [], None
for k, w in enumerate(words):
    core = w["w"].strip(" ")
    if re.fullmatch(r"\d+", core.rstrip(",")) or re.fullmatch(r",\d+,?", core):
        if cur and (re.fullmatch(r",\d+,?", core)) and w["s"] - words[cur[1]]["e"] < 0.8:
            cur[1] = k
            continue
        if cur:
            amounts.append(cur)
        cur = [k, k]
    else:
        if cur:
            amounts.append(cur)
        cur = None
if cur:
    amounts.append(cur)
for a, b in zip(amounts, amounts[1:]):
    big = lambda r: "".join(words[x]["w"] for x in range(r[0], r[1] + 1)).count(",") >= 1
    if a[1] + 1 == b[0] and big(a) and big(b) and words[b[0]]["s"] - words[a[1]]["e"] < 1.5:
        drops.append((words[a[0]]["s"] - 0.05, words[b[0]]["s"] - 0.05,
                      "corrected number: " + "".join(words[x]["w"] for x in range(a[0], a[1] + 1))))

drops.sort()
keep, t = [], max(0.0, words[0]["s"] - 0.1)
for a, b, why in drops:
    if a - t > 0.2:
        keep.append([round(t, 2), round(a, 2)])
    t = max(t, b)
    print(f"DROP {a:7.2f} - {b:7.2f}  {why}")
keep.append([round(t, 2), round(words[-1]["e"] + 0.3, 2)])
json.dump({"keep": keep, "drops": [{"start": round(a, 2), "end": round(b, 2), "why": w} for a, b, w in drops]},
          open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("keep:", keep)
