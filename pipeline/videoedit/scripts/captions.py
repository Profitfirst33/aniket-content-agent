"""Turn the cut transcript into Hinglish (Roman) caption chunks.

Usage: python captions.py <cut_words.json> <captions.json> [roman_extra.json]

- Devanagari words are written in Roman Hinglish (ROMAN map below, plus roman_extra.json for this video).
  Devanagari words with no mapping are listed in <captions>.unknown.json: fill them into roman_extra.json
  ({"देवनागरी": "roman"}) and run again until that list is empty.
- Whisper splits numbers ("9" ",43" ",959" "रुपीज"); they are merged into one "₹9,43,959" token.
- Words are grouped 2-4 per chunk, breaking at punctuation, gaps > 0.3 s or ~20 characters.
Each word gets a kind: "num" (₹ / %), "neg" (nahi, kam ...) or "" for styling.
"""
import json
import re
import sys

ROMAN = {
    "मैंने": "maine", "इस": "is", "साल": "saal", "का": "ka", "जमा": "jama", "किया": "kiya", "है": "hai",
    "कल": "kal", "जब": "jab", "मैं": "main", "अपनी": "apni", "देख": "dekh", "रहा": "raha", "था": "tha",
    "तो": "toh", "सोचा": "socha", "कि": "ki", "एक": "ek", "निकालते": "nikaalte", "हैं": "hain", "मेरे": "mere",
    "खून": "khoon", "पसेने": "paseene", "की": "ki", "कमाई": "kamaai", "को": "ko", "सरकार": "sarkaar", "ने": "ne",
    "कहां": "kahan", "खर्च": "kharch", "और": "aur", "ये": "ye", "भारत": "Bharat", "के": "ke",
    "मुताबिक": "mutaabik", "बना": "bana", "हूँ": "hoon", "पूरे": "poore", "में": "mein", "डाल": "daal",
    "दिया": "diya", "सबसे": "sabse", "पहले": "pehle", "यानि": "yaani", "यानी": "yaani", "टैक्स": "tax",
    "से": "se", "सीधा": "seedha", "अलग": "alag", "स्टेट्स": "states", "चला": "chala", "गया": "gaya",
    "उनके": "unke", "लोकल": "local", "डेवलप्मेंट": "development", "इंफरस्ट्रक्शर": "infrastructure",
    "लिए": "liye", "सेकंड": "second", "उन": "un", "पुराने": "puraane", "कर्जों": "karzon",
    "इंटरेस्ट": "interest", "चुकाने": "chukaane", "जो": "jo", "देश": "desh", "पर": "par",
    "अलरेड़ी": "already", "चल": "chal", "रहे": "rahe", "तीसरा": "teesra", "जिससे": "jisse", "नए": "naye",
    "बन": "ban", "चौथा": "chautha", "गए": "gaye", "हमारी": "hamaari", "हमारे": "hamaare", "ताकि": "taaki",
    "बिल्कुल": "bilkul", "सुरक्षित": "surakshit", "फिफ्ट": "paanchva", "हुए": "hue", "हुआ": "hua",
    "जैसे": "jaise", "योजना": "Yojana", "Mandrega": "MGNREGA", "आती": "aati", "छटा": "chhatha",
    "एरिया": "area", "चले": "chale", "ग्राम": "Gram", "पंचायत": "Panchayat", "अगला": "agla",
    "चलाना": "chalaana", "करोड": "crore", "लोगों": "logon", "राशन": "ration", "मिलता": "milta",
    "मिलती": "milti", "आखरी": "aakhri", "अगर": "agar", "इसका": "iska", "पूरा": "poora",
    "विशलेशन": "analysis", "करूँ": "karoon", "मुझे": "mujhe", "समझ": "samajh", "आता": "aata",
    "अभी": "abhi", "भी": "bhi", "हमारा": "hamaara", "बहुत": "bahut", "सारा": "saara", "पैसा": "paisa",
    "वो": "vo", "जाता": "jaata", "यहाँ": "yahan", "पे": "pe", "ही": "hi", "कम": "kam", "सोचिए": "sochiye",
    "दो": "do", "नीचे": "neeche", "आया": "aaya", "तक": "tak", "नहीं": "nahi", "ऐसी": "aisi",
    "चीजे": "cheezein", "प्राथमिक्ता": "priority", "बताती": "bataati", "जिस": "jis", "तरीके": "tareeke",
    "हम": "hum", "करेंगे": "karenge", "उसी": "usi", "आगे": "aage", "बनेंगे": "banenge", "आपको": "aapko",
    "क्या": "kya", "लगता": "lagta", "कौन": "kaun", "सी": "si", "चीजों": "cheezon", "ज़्यादा": "zyada",
    "करना": "karna", "चाहिए": "chahiye", "अपना": "apna", "करके": "karke", "चलना": "chalna",
    "बताना": "batana", "आप": "aap", "बताओ": "batao", "भाई": "bhai", "आपका": "aapka", "कितना": "kitna",
    "आजाएगा": "aa jaayega", "काम": "kaam", "बाकी": "baaki", "height": "belt", "defense": "defence",
}
if len(sys.argv) > 3:
    ROMAN.update(json.load(open(sys.argv[3], encoding="utf-8")))
RUPEE = {"रुपीज", "रुपे", "रुपये", "रुपए"}
PERCENT = {"%", "परसेंट"}
NEG = {"nahi", "kam", "neeche"}


def split_punct(w):
    m = re.match(r"^(-?)(.*?)([,.?]*)$", w)
    return m.group(1), m.group(2), m.group(3)


words = json.load(open(sys.argv[1], encoding="utf-8"))
toks = []  # {t, s, e, kind, brk}
for w in words:
    lead, core, punct = split_punct(w["text"].strip())
    last = toks[-1] if toks else None
    if last and ROMAN.get(core, core) == last["t"].rstrip(",.") and w["start"] - last["e"] < 0.1:  # whisper doubled a word
        last["e"] = w["end"]
        continue
    if last and last["kind"] == "digits" and re.fullmatch(r"\d+", core):  # "20 1,88,792": the 20 is a percent
        last["t"] += "%"
        last["kind"] = "pct"
    if last and re.fullmatch(r",\d+", core) and last["kind"] in ("num", "digits"):
        last["t"] += core
        last["e"] = w["end"]
        last["kind"] = "num"
        last["brk"] = bool(punct)
        continue
    if last and core in PERCENT and last["kind"] in ("digits", "pct"):
        if last["kind"] == "digits":
            last["t"] += "%"
        last["kind"] = "pct"
        last["e"] = w["end"]
        last["brk"] = bool(punct) or last["brk"]
        continue
    if core in PERCENT and last and last["t"].endswith("%"):
        last["e"] = w["end"]
        continue
    if last and core in RUPEE and last["kind"] == "num":
        last["t"] = "₹" + last["t"]
        last["e"] = w["end"]
        last["brk"] = bool(punct)
        continue
    text = ROMAN.get(core, core)
    if core in RUPEE:
        text = "rupees"
    if core in PERCENT:
        text = "percent"
    kind = "digits" if re.fullmatch(r"\d+", core) else ""
    if core == "-कहां" or lead == "-":
        text = "-" + ROMAN.get(core.lstrip("-"), core.lstrip("-"))
    toks.append({"t": text + ("," if punct.startswith(",") else ""), "s": w["start"], "e": w["end"],
                 "kind": kind, "brk": bool(punct)})

for k in toks:
    if k["kind"] == "num" and "," in k["t"] and not k["t"].startswith("₹"):
        k["t"] = "₹" + k["t"]
    if k["kind"] in ("digits", "pct", "num"):
        k["kind"] = "num"
    elif k["t"].strip(",.").lower() in NEG:
        k["kind"] = "neg"
    # "kahan -kahan" reads better joined
for i in range(len(toks) - 1, 0, -1):
    if toks[i]["t"].startswith("-"):
        toks[i - 1]["t"] = toks[i - 1]["t"].rstrip(",") + toks[i]["t"]
        toks[i - 1]["e"] = toks[i]["e"]
        toks[i - 1]["brk"] = toks[i]["brk"]
        del toks[i]

chunks, cur = [], []
for i, k in enumerate(toks):
    if cur:
        gap = k["s"] - cur[-1]["e"]
        chars = sum(len(x["t"]) + 1 for x in cur) + len(k["t"])
        if cur[-1]["brk"] or gap > 0.3 or len(cur) >= 4 or chars > 20 or k["kind"] == "num" and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    cur.append(k)
if cur:
    chunks.append(cur)

# a 1-2 word chunk under 0.45 s flashes by: fold it into a neighbour when the gap is small
merged = []
for c in chunks:
    short = len(c) <= 2 and c[-1]["e"] - c[0]["s"] < 0.45
    if short and merged and len(merged[-1]) + len(c) <= 5 and c[0]["s"] - merged[-1][-1]["e"] < 0.35:
        merged[-1].extend(c)
    else:
        merged.append(c)
chunks = merged

out = []
for i, c in enumerate(chunks):
    nxt = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else c[-1]["e"] + 0.4
    out.append({"start": round(c[0]["s"], 3), "end": round(min(nxt, c[-1]["e"] + 0.5), 3),
                "words": [{"t": k["t"].rstrip(","), "s": round(k["s"], 3), "e": round(k["e"], 3), "kind": k["kind"]}
                          for k in c]})
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
unknown = sorted({w["t"].strip(",.-") for c in out for w in c["words"] if re.search(r"[\u0900-\u097F]", w["t"])})
json.dump(unknown, open(sys.argv[2].replace(".json", "") + ".unknown.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"{len(toks)} tokens -> {len(out)} chunks; {len(unknown)} Devanagari words still need Roman spelling")
