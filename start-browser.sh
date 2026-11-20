#!/usr/bin/env bash
# Content Agent browser: separate desktop (:91), VNC (5902), noVNC (6082), Chrome CDP (9225)
set -euo pipefail

export DISPLAY=:91
export HOME=/var/lib/aniket-content-agent

pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

/usr/bin/Xvfb :91 -screen 0 1440x900x24 -nolisten tcp &
pids+=("$!")

for _ in {1..30}; do
  [[ -S /tmp/.X11-unix/X91 ]] && break
  sleep 0.2
done
[[ -S /tmp/.X11-unix/X91 ]]

/usr/bin/openbox &
pids+=("$!")

/usr/bin/x11vnc -display :91 -forever -shared -localhost -rfbport 5902 -nopw -quiet &
pids+=("$!")

/usr/bin/websockify --web=/usr/share/novnc 127.0.0.1:6082 127.0.0.1:5902 &
pids+=("$!")

/usr/bin/google-chrome \
  --no-first-run \
  --no-default-browser-check \
  --disable-gpu \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9225 \
  --user-data-dir=/var/lib/aniket-content-agent/chrome-profile \
  --window-size=1440,900 \
  --start-maximized \
  https://www.instagram.com/ https://labs.google/fx/tools/flow &
pids+=("$!")

wait -n "${pids[@]}"
