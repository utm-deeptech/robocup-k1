#!/usr/bin/env python3
"""Restart a specific stalled Studio native camera renderer, retaining its setup.

Run on the host with the renderer PID. This does not restart the simulator.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('pid', type=int)
args = parser.parse_args()
proc = Path('/proc') / str(args.pid)
argv = [part.decode() for part in (proc / 'cmdline').read_bytes().split(b'\0') if part]
if Path(argv[0]).name != 'booster-camera-renderer':
    raise SystemExit('PID is not the Booster camera renderer')
env = dict(part.decode().split('=', 1) for part in (proc / 'environ').read_bytes().split(b'\0') if b'=' in part)
workdir = os.readlink(proc / 'cwd')
os.kill(args.pid, signal.SIGTERM)
for _ in range(50):
    if not proc.exists() or (proc / 'stat').read_text().split()[2] == 'Z':
        break
    time.sleep(0.1)
else:
    raise SystemExit('Renderer did not stop; no replacement launched')
time.sleep(1)
for path in Path('/proc').iterdir():
    if not path.name.isdigit() or int(path.name) == args.pid:
        continue
    try:
        other = (path / 'cmdline').read_bytes().split(b'\0')
        if other and other[0] == argv[0].encode() and b'--physics-url' in other:
            if argv[argv.index('--physics-url') + 1].encode() in other:
                print(json.dumps({'stage': 'studio_restarted_renderer', 'pid': int(path.name)}))
                raise SystemExit(0)
    except (PermissionError, FileNotFoundError, ProcessLookupError):
        pass
log_path = Path(__file__).resolve().parents[1] / 'sim-camera-renderer.log'
with log_path.open('ab') as log:
    child = subprocess.Popen(argv, env=env, cwd=workdir, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print(json.dumps({'stage': 'renderer_restarted', 'pid': child.pid, 'log': str(log_path)}))
