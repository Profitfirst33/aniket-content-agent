#!/usr/bin/env bash
# One-time installer for the Content Agent on a fresh Ubuntu 24.04+ VPS (run as root).
# Usage:  git clone <this repo> /opt/aniket-content-agent && bash /opt/aniket-content-agent/deploy/install.sh
set -euo pipefail

APP=/opt/aniket-content-agent
DATA=/var/lib/aniket-content-agent

[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }
[[ -d $APP/pipeline ]] || { echo "Clone this repo to $APP first"; exit 1; }

echo "==> System packages"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl git ca-certificates python3 python3-venv python3-pip ffmpeg \
  xvfb openbox x11vnc websockify novnc fonts-noto fonts-noto-color-emoji

echo "==> Google Chrome"
if ! command -v google-chrome >/dev/null; then
  curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  apt-get install -y /tmp/chrome.deb && rm -f /tmp/chrome.deb
fi

echo "==> Node.js (LTS) + global tools"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
  apt-get install -y nodejs
fi
npm install -g --prefix /usr hyperframes@0.8.223 @playwright/mcp@0.0.83

echo "==> Claude Code CLI"
if [[ ! -x /root/.local/bin/claude ]]; then
  curl -fsSL https://claude.ai/install.sh | bash
fi

echo "==> Python venv"
python3 -m venv $APP/venv
$APP/venv/bin/pip install --upgrade pip
$APP/venv/bin/pip install -r $APP/requirements.txt

echo "==> Logo icons"
(cd $APP/pipeline/logos && npm ci)

echo "==> Agent user + data folder"
id aniket-agent >/dev/null 2>&1 || useradd --system --home $DATA --shell /usr/sbin/nologin aniket-agent
mkdir -p $DATA/jobs $DATA/outbox $DATA/work $DATA/Downloads
cp -n $APP/data-template/work/* $DATA/work/ || true
chown -R aniket-agent:aniket-agent $DATA
chmod 700 $DATA
chmod +x $APP/start-browser.sh $APP/pipeline/*.sh

echo "==> Connect Claude to the agent's Chrome (browser MCP)"
/root/.local/bin/claude mcp add --scope user content-browser -- /usr/bin/playwright-mcp --cdp-endpoint http://127.0.0.1:9225 || true

echo "==> Services"
cp $APP/deploy/aniket-content-agent-browser.service /etc/systemd/system/
cp $APP/deploy/aniket-content-agent-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now aniket-content-agent-browser.service
systemctl enable aniket-content-agent-bot.service   # starts once telegram.json exists

cat <<'EOF'

Install done. Next steps (see README.md):
  1. /root/.local/bin/claude          -> log in to your Claude account once, then /exit
  2. bash /opt/aniket-content-agent/pipeline/set_telegram_token.sh
  3. Send /start to your bot in Telegram, then:
     python3 /opt/aniket-content-agent/pipeline/deliver.py --setup
  4. Open the agent's browser (SSH tunnel to port 6082) and log in to Instagram + Google Flow
  5. systemctl restart aniket-content-agent-bot
EOF
