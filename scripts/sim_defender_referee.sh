#!/bin/bash
# Run inside the existing container. Replace only the built-in referee worker.
# Keep the official referee implementation, assigning robot2 to the away side.
set -e
cd "$(dirname "$0")/.."
repo_dir="$PWD"
python3 - "$repo_dir" <<'PY'
import os
from pathlib import Path
import signal
import sys
import time
helper = (sys.argv[1] + "/scripts/sim_defender_referee.py").encode()
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():
        continue
    try:
        argv = (proc / 'cmdline').read_bytes().split(b'\0')
        if (proc / 'comm').read_text().strip() == 'bs-ext-game-con' or helper in argv:
            os.kill(int(proc.name), signal.SIGTERM)
            print('Stopped previous referee worker:', proc.name, flush=True)
    except (FileNotFoundError, ProcessLookupError):
        pass
time.sleep(2)
PY
mkdir -p .cache/defender-referee
cd /usr/local/booster_robot/booster_robocup_sim
exec .venv/bin/python -u "$repo_dir/scripts/sim_defender_referee.py" \
    --result-dir "$repo_dir/.cache/defender-referee" \
    --runtime-dir "$repo_dir/.cache/defender-referee/runtime" \
    --no-team-ready --ready-timeout-ms 60000 --settle-ms 2000 \
    --home-team-number 1 --away-team-number 2 --players-per-team 3 \
    --home-robots robot1:1,robot3:2,robot5:3 \
    --away-robots robot2:1,robot4:2,robot6:3
