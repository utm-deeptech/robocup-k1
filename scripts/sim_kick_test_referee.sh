#!/bin/bash
# Temporary measurement referee; restore sim_defender_referee.sh after testing.
set -e
cd "$(dirname "$0")/.."
repo_dir="$PWD"
python3 - "$repo_dir" <<'PY'
import os
from pathlib import Path
import signal
import shlex
import sys
import time
helpers = {(sys.argv[1] + '/scripts/' + name) for name in
           ('sim_defender_referee.py', 'sim_kick_test_referee.py')}
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():
        continue
    try:
        # Simulator process titles can replace argv with one space-separated string.
        argv = shlex.split((proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'))
        if (proc / 'comm').read_text().strip() == 'bs-ext-game-con' or helpers.intersection(argv):
            os.kill(int(proc.name), signal.SIGTERM)
            print('Stopped previous referee worker:', proc.name, flush=True)
    except (FileNotFoundError, ProcessLookupError, ValueError):
        pass
time.sleep(2)
PY
mkdir -p .cache/kick-test-referee
cd /usr/local/booster_robot/booster_robocup_sim
exec .venv/bin/python -u "$repo_dir/scripts/sim_kick_test_referee.py" \
    --result-dir "$repo_dir/.cache/kick-test-referee" \
    --runtime-dir "$repo_dir/.cache/kick-test-referee/runtime" \
    --no-team-ready --ready-timeout-ms 60000 --settle-ms 2000 \
    --home-team-number 1 --away-team-number 2 --players-per-team 3 \
    --home-robots robot1:1,robot3:2,robot5:3 \
    --away-robots robot2:1,robot4:2,robot6:3
