#!/usr/bin/env python3
"""Read posting options out of the Telegram note sent with a reel.

  "collab @anantgupta tag @wisprflow trial"  ->
  {"collab": ["anantgupta"], "tag": ["wisprflow"], "trial": "manual", "rest": ""}

Rules: "collab"/"collaborator" and "tag" each take the @handles that follow them.
A bare @handle with no keyword counts as a tag. "trial" = manual trial, "trial auto" = auto.
Everything else is returned as "rest" (it stays a note for the script writer).
"""
import re, sys, json

HANDLE = re.compile(r"@([A-Za-z0-9_.]{1,30})")


def parse(note):
    out = {"collab": [], "tag": [], "trial": None, "rest": ""}
    words, rest, mode = (note or "").split(), [], None
    i = 0
    while i < len(words):
        w = words[i]
        lw = w.lower().strip(",.:;")
        if lw in ("collab", "collabs", "collaborator", "collaborators"):
            mode = "collab"
        elif lw in ("tag", "tags"):
            mode = "tag"
        elif lw == "trial":
            out["trial"] = "manual"
            if i + 1 < len(words) and words[i + 1].lower().strip(",.") in ("auto", "automatic"):
                out["trial"] = "auto"
                i += 1
            mode = None
        elif HANDLE.fullmatch(w.strip(",.;:")):
            h = HANDLE.fullmatch(w.strip(",.;:")).group(1)
            bucket = out[mode or "tag"]
            if h.lower() not in [x.lower() for x in bucket]:
                bucket.append(h)
        elif mode and lw in ("and", "with", "&"):
            pass  # "collab @a and @b": the joiner belongs to the list
        else:
            mode = None
            rest.append(w)
        i += 1
    out["rest"] = " ".join(rest).strip()
    return out


if __name__ == "__main__":
    print(json.dumps(parse(" ".join(sys.argv[1:])), ensure_ascii=False))
