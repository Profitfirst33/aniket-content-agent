#!/usr/bin/env bash
# Make one reel now and send it to Telegram when done.
# usage: new_reel.sh "topic, idea or reel link"
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
[ $# -ge 1 ] || { echo 'usage: new_reel.sh "topic, idea or reel link"'; exit 1; }
JOB="/var/lib/aniket-content-agent/jobs/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$JOB"
printf '%s\n' "$*" > "$JOB/request.txt"
exec 9>/tmp/content-agent.lock
flock -n 9 || { echo "another reel is being made, try later"; exit 1; }
python3 /opt/aniket-content-agent/pipeline/run_reel.py "$JOB" 2>&1 | tee -a "$JOB/run.out"
