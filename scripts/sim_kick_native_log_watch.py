#!/usr/bin/env python3
"""Preserve native motion logs between completed trials, without robot input."""
import argparse
import json
from pathlib import Path
import shutil
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--trials',type=int,default=20)
    args = parser.parse_args()
    results = args.output/'results.json'
    done = len(json.loads(results.read_text())) if results.exists() else 0
    deadline = time.monotonic()+7200
    while done < args.trials and time.monotonic() < deadline:
        try:
            rows=json.loads(results.read_text())
        except (FileNotFoundError, ValueError):
            time.sleep(.1)
            continue
        if len(rows)>done:
            trial=rows[-1]['trial']
            for name in ('robot1.log','robot1_rsp.log'):
                path=Path('/usr/local/booster_robot/booster_robocup_sim/logs')/name
                if path.exists():
                    shutil.copyfile(path,args.output/f'trial-{trial:02d}-native-{name}')
            done=len(rows)
            print(json.dumps({'saved_native_logs_for_trial':trial}),flush=True)
        time.sleep(.1)


if __name__=='__main__':
    main()
