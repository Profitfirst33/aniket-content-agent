#!/usr/bin/env python3
"""Send a finished reel to the user's Telegram.

usage: deliver.py <video.mp4> "<caption>"     send a reel
       deliver.py --setup                     find the chat id after the user sent /start to the bot
Config: /opt/aniket-content-agent/telegram.json  {"token": "<bot token from @BotFather>", "chat_id": "<filled by --setup>"}
The user writes the token into that file themselves.
"""
import json, os, subprocess, sys

CFG = "/opt/aniket-content-agent/telegram.json"


def api(cfg, method, *form):
    args = ["curl", "-s", f"https://api.telegram.org/bot{cfg['token']}/{method}"]
    for f in form:
        args[2:2] = ["-F", f]
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    return json.loads(r.stdout or "{}")


def setup():
    cfg = json.load(open(CFG))
    upd = api(cfg, "getUpdates").get("result", [])
    chats = [u["message"]["chat"] for u in upd if "message" in u]
    if not chats:
        print("no messages yet: open your bot in Telegram, send /start, then run --setup again")
        return 1
    cfg["chat_id"] = str(chats[-1]["id"])
    json.dump(cfg, open(CFG, "w"))
    os.chmod(CFG, 0o600)
    api(cfg, "sendMessage", f"chat_id={cfg['chat_id']}", "text=Content Agent connected. Naye reels yahan aayenge.")
    print("chat id saved for", chats[-1].get("first_name") or chats[-1].get("title"))
    return 0


def send(video, caption):
    if not os.path.exists(CFG):
        print(f"telegram not set up ({CFG} missing); reel stays in the outbox")
        return 0
    cfg = json.load(open(CFG))
    if not cfg.get("chat_id"):
        print("telegram chat id missing: run deliver.py --setup")
        return 1
    r = api(cfg, "sendVideo", f"chat_id={cfg['chat_id']}", f"caption={caption[:1000]}",
            "supports_streaming=true", f"video=@{video}")
    print("telegram:", "sent" if r.get("ok") else str(r)[:300])
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--setup"]:
        sys.exit(setup())
    sys.exit(send(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
