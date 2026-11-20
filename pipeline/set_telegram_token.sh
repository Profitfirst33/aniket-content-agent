#!/usr/bin/env bash
# Asks for the Telegram bot token (hidden input) and saves it for the content agent.
set -euo pipefail
read -rsp "Telegram bot token paste karo aur Enter dabao: " T
echo
if ! [[ "$T" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then
  echo "Ye token sahi format mein nahi lag raha (jaise 1234567890:AAH...). Dobara chalao."
  exit 1
fi
umask 077
printf '{"token": "%s"}\n' "$T" > /opt/aniket-content-agent/telegram.json
echo "Token save ho gaya. Ab Telegram mein apne bot ko /start bhejo."
