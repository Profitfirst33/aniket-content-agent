#!/usr/bin/env python3
"""Post to the Aniket AI Instagram through the Instagram API with Instagram Login.

usage:
  post.py <job_dir | media files...> --type reel|carousel|image|story
          [--trial manual|auto] [--tag @a ...] [--collab @a ...] [--caption-file f] [--dry-run]
  post.py --refresh-token          renew the 60 day token (run every ~50 days)

Every container is created with is_ai_generated=true (Meta's "AI info" label, create time only).
Media is copied to a public folder (PUBLIC_DIR, served at PUBLIC_URL) so Instagram can fetch it,
and removed again after publishing. Result is one JSON object on stdout.
Config: /opt/aniket-content-agent/autopost/ig.json  {"token": "...", "ig_user_id": "...",
        "public_dir": "...", "public_url": "https://.../"}
"""
import argparse, glob, json, os, shutil, subprocess, sys, time, urllib.parse, urllib.request, uuid

HERE = "/opt/aniket-content-agent/autopost"
CFG_PATH = f"{HERE}/ig.json"
API = "https://graph.instagram.com/v23.0"
AUDIO_NAME = "Aniket AI · Original audio"
VIDEO_EXT = (".mp4", ".mov")
DRY = False


def cfg():
    if not os.path.exists(CFG_PATH):
        if DRY:
            return {"token": "<TOKEN>", "ig_user_id": "<IG_USER_ID>",
                    "public_dir": f"{HERE}/public", "public_url": "https://YOUR-DOMAIN/ig-media/"}
        sys.exit(f"missing {CFG_PATH} (copy ig.example.json and fill it)")
    return json.load(open(CFG_PATH))


def req(method, path, params, c):
    """One Graph call. In dry-run, print it (token masked) and return a fake answer."""
    url = path if path.startswith("http") else f"{API}/{path}"
    shown = {k: v for k, v in params.items()}
    if DRY:
        print(json.dumps({"dry_run": True, "method": method, "url": url, "params": shown}, ensure_ascii=False), file=sys.stderr)
        fake = {"id": f"DRY{uuid.uuid4().hex[:8]}"}
        if "fields" in params:
            fake.update(status_code="FINISHED", is_ai_generated=True, permalink="https://www.instagram.com/reel/DRYRUN/")
        return fake
    params = dict(params, access_token=c["token"])
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        r = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        r = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(json.dumps({"ok": False, "step": path, "error": e.read().decode()[:800]}))


def publish_url(path, c):
    """Copy a file into the public folder, PNG/WEBP become JPEG. Returns (public url, local copy)."""
    os.makedirs(c["public_dir"], exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(path))
    name = f"{uuid.uuid4().hex[:12]}"
    if ext.lower() in (".png", ".webp", ".jpeg", ".jpg") and ext.lower() != ".jpg":
        out = f"{c['public_dir']}/{name}.jpg"
        if not DRY:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-q:v", "2", out], check=True)
    else:
        out = f"{c['public_dir']}/{name}{ext.lower()}"
        if not DRY:
            shutil.copy(path, out)
    return c["public_url"].rstrip("/") + "/" + os.path.basename(out), out


def handles(xs):
    return [x.lstrip("@").strip() for x in xs or [] if x.strip("@ ")]


def wait_ready(cid, c):
    for _ in range(100):
        st = req("GET", cid, {"fields": "status_code,status"}, c)
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(json.dumps({"ok": False, "step": "processing", "error": st}))
        time.sleep(6)
    raise SystemExit(json.dumps({"ok": False, "step": "processing", "error": "timeout"}))


def find_media(target, kind):
    """A job dir gives its finished reel (output/*.mp4); otherwise the files given."""
    if len(target) == 1 and os.path.isdir(target[0]):
        vids = sorted(glob.glob(f"{target[0]}/output/*.mp4"))
        if not vids:
            sys.exit(f"no output/*.mp4 in {target[0]}")
        return vids[-1:]
    return target


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("media", nargs="*")
    ap.add_argument("--type", choices=["reel", "carousel", "image", "story"])
    ap.add_argument("--trial", choices=["manual", "auto"])
    ap.add_argument("--tag", nargs="*", default=[])
    ap.add_argument("--collab", nargs="*", default=[])
    ap.add_argument("--caption-file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh-token", action="store_true")
    a = ap.parse_args()
    DRY = a.dry_run
    c = cfg()

    if a.refresh_token:
        r = req("GET", "https://graph.instagram.com/refresh_access_token", {"grant_type": "ig_refresh_token"}, c)
        if not DRY and r.get("access_token"):
            c["token"], c["token_expires_at"] = r["access_token"], int(time.time()) + int(r.get("expires_in", 0))
            tmp = CFG_PATH + ".tmp"
            json.dump(c, open(tmp, "w"), indent=1)
            os.chmod(tmp, 0o600)
            os.replace(tmp, CFG_PATH)
        print(json.dumps({"ok": True, "refreshed": True, "expires_in": r.get("expires_in")}))
        return

    if not a.type or not a.media:
        ap.error("media and --type are needed")
    files = find_media(a.media, a.type)
    caption = open(a.caption_file).read().strip() if a.caption_file else ""
    if not caption and len(a.media) == 1 and os.path.isfile(f"{a.media[0]}/caption.txt"):
        caption = open(f"{a.media[0]}/caption.txt").read().strip()
    tags, collabs = handles(a.tag), handles(a.collab)
    if len(collabs) > 3:
        sys.exit("Instagram allows at most 3 collaborators")
    if a.type == "story" and (tags or collabs or a.trial):
        sys.exit("stories cannot carry tags, collaborators or trial settings through the API")
    if a.trial and a.type != "reel":
        sys.exit("trial is for reels only")

    me, made = c["ig_user_id"], []
    try:
        if a.type == "carousel":
            if not 2 <= len(files) <= 10:
                sys.exit("a carousel needs 2 to 10 files")
            kids = []
            for f in files:
                url, local = publish_url(f, c)
                made.append(local)
                p = {"is_carousel_item": "true"}
                p.update({"media_type": "VIDEO", "video_url": url} if f.lower().endswith(VIDEO_EXT) else {"image_url": url})
                kid = req("POST", f"{me}/media", p, c)["id"]
                wait_ready(kid, c)
                kids.append(kid)
            p = {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption, "is_ai_generated": "true"}
        else:
            if len(files) != 1:
                sys.exit(f"{a.type} takes exactly one file")
            url, local = publish_url(files[0], c)
            made.append(local)
            video = files[0].lower().endswith(VIDEO_EXT)
            if a.type == "reel":
                if not video:
                    sys.exit("a reel needs an mp4 or mov")
                p = {"media_type": "REELS", "video_url": url, "caption": caption, "audio_name": AUDIO_NAME,
                     "share_to_feed": "true", "is_ai_generated": "true"}
                if a.trial:
                    p["trial_params"] = json.dumps({"graduation_strategy": "MANUAL" if a.trial == "manual" else "SS_PERFORMANCE"})
            elif a.type == "story":
                p = {"media_type": "STORIES", "is_ai_generated": "true"}
                p.update({"video_url": url} if video else {"image_url": url})
            else:
                if video:
                    sys.exit("use --type reel for a video")
                p = {"image_url": url, "caption": caption, "is_ai_generated": "true"}
        if tags:
            # reels take usernames only; images need a position, so tags sit in the middle
            p["user_tags"] = json.dumps([{"username": t} if a.type == "reel" else {"username": t, "x": 0.5, "y": 0.5} for t in tags])
        if collabs and a.type != "story":
            p["collaborators"] = json.dumps(collabs)
        cid = req("POST", f"{me}/media", p, c)["id"]
        wait_ready(cid, c)
        mid = req("POST", f"{me}/media_publish", {"creation_id": cid}, c)["id"]
        info = req("GET", mid, {"fields": "permalink,is_ai_generated,media_product_type,timestamp"}, c)
    finally:
        if not DRY:
            for f in made:
                try:
                    os.remove(f)
                except OSError:
                    pass
    print(json.dumps({"ok": True, "dry_run": DRY, "type": a.type, "media_id": mid,
                      "permalink": info.get("permalink"), "ai_label": bool(info.get("is_ai_generated")),
                      "trial": a.trial, "tags": tags, "collaborators": collabs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
