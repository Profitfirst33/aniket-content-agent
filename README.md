# Content Agent (Telegram → AI avatar reel)

Send an Instagram reel link (or `/topic <topic>`) to your Telegram bot. The agent reads the reel,
writes a script with Claude, generates avatar clips in **Google Flow** inside its own Chrome,
edits everything (captions, b-roll, logos, music) and sends the finished reel back to Telegram.

## What runs on the server

| Part | What it does |
|---|---|
| `aniket-content-agent-browser.service` | Chrome on a virtual screen (Xvfb `:91`), viewable via noVNC on `127.0.0.1:6082`, Chrome debug port `9225` |
| `aniket-content-agent-bot.service` | `pipeline/bot.py` – Telegram inbox and reel queue |
| `pipeline/run_reel.py` | one reel, end to end (Claude CLI + Flow + ffmpeg + hyperframes) |
| `autopost/` | Instagram auto-posting (built, **not connected** to the bot yet) |

Code lives in `/opt/aniket-content-agent`, data (Chrome profile, jobs, output) in `/var/lib/aniket-content-agent`.
These paths are hard-coded, so keep them.

## You need (your own accounts)

- A VPS: **Ubuntu 24.04+**, root SSH, at least **4 GB RAM** (8 GB better), 2+ CPU, 80 GB+ disk
- A **Claude** account (Pro/Max) for Claude Code
- A **Google account with Google Flow** access and credits, with your own avatar ("Me" ingredient) set up
- An **Instagram** account (used in the browser for research)
- A **Telegram bot** token from @BotFather

## Install

```bash
# on the VPS, as root
git clone <this-repo-url> /opt/aniket-content-agent
bash /opt/aniket-content-agent/deploy/install.sh
```

Then:

1. **Log in to Claude:** run `/root/.local/bin/claude`, finish the login, type `/exit`.
2. **Telegram token:** `bash /opt/aniket-content-agent/pipeline/set_telegram_token.sh` (paste the BotFather token).
3. **Link your chat:** send `/start` to your bot in Telegram, then
   `python3 /opt/aniket-content-agent/pipeline/deliver.py --setup`
4. **Open the agent's browser** from your laptop:
   ```bash
   ssh -N -L 6082:127.0.0.1:6082 root@YOUR_VPS_IP
   ```
   Open <http://localhost:6082/vnc.html?autoconnect=true&resize=scale>, then log in to Instagram and to
   Google Flow (labs.google/fx/tools/flow) inside that Chrome.
5. **Your avatar and Flow project:** edit `/var/lib/aniket-content-agent/work/flow-settings.json`
   (`project` = your Flow project name) and replace `work/aniket-avatar.jpg` with your own face photo.
   Also review the prompts in `pipeline/prompts/` (style, name, call-to-action) for your brand.
6. **Start the bot:** `systemctl restart aniket-content-agent-bot`, then send a reel link to your bot.

## Useful commands

```bash
systemctl status aniket-content-agent-browser aniket-content-agent-bot
journalctl -u aniket-content-agent-bot -f          # live bot log
ls /var/lib/aniket-content-agent/jobs              # one folder per reel
```

Telegram commands: `/status /queue /pause /resume /clear /topic /help`.

## Notes

- The noVNC screen has **no password**; it is only reachable through SSH. Never open port 6082/5902/9225 in the firewall.
- Never commit `telegram.json` or `autopost/ig.json` (already in `.gitignore`).
- One Telegram bot token can only run on one server at a time.
- If `reel_read.mjs` cannot find `playwright-core`, check the path under `/usr/lib/node_modules/@playwright/mcp/node_modules/`.
- `*.bak-*` files are older versions kept for reference; the agent does not use them.
