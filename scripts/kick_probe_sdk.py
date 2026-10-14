#!/usr/bin/env python3
"""Test-only: does the kick work through Booster's own SoccerKickManager path?

Same call sequence as Booster's default 3v3 AI: BoosterRobot(robot1) ->
SoccerKickManager.start() (ChangeMode kSoccer + VisualKick kV2) ->
update_command(direction, power) + update_ball(x, y) streamed at 20 Hz.
Truth is used only to place the ball and to measure the result.
"""
import argparse
import json
import math
import subprocess
import threading
import time

from boosteros.robots.booster import BoosterRobot
from boosteros.robots.booster._motion.soccer_kick import SoccerKickManager

SIM_PY = '/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python'
WORKER = '/root/robocup_demo/scripts/sim_kick_physics_worker.py'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dist', type=float, default=1.0)
    p.add_argument('--power', type=float, default=1.5)
    p.add_argument('--seconds', type=float, default=10.0)
    p.add_argument('--no-place', action='store_true')
    a = p.parse_args()

    worker = subprocess.Popen([SIM_PY, WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    latest = {}

    def read():
        for line in worker.stdout:
            msg = json.loads(line)
            if msg.get('kind') == 'world':
                latest['w'] = msg['world']
    threading.Thread(target=read, daemon=True).start()
    while 'w' not in latest:
        time.sleep(0.05)

    def r1():
        return next(r for r in latest['w']['robots'] if r['name'] == 'robot1')

    robot = BoosterRobot(virtual_robot_name='', enable_tf_listener=False, timeout=10.0)
    print('mode before:', robot.get_mode(), flush=True)
    if robot.get_mode() in ('damping', 'custom'):
        robot.set_mode('prepare')
        time.sleep(3.0)
    r = r1()
    yaw = r['yaw']
    ball0 = [r['position'][0] + a.dist * math.cos(yaw), r['position'][1] + a.dist * math.sin(yaw), 0.11]
    if a.no_place:
        ball0 = list(latest['w']['ballPosition'])
    else:
        worker.stdin.write(json.dumps({'command': 'place_ball', 'position': ball0}) + '\n')
        worker.stdin.flush()
        time.sleep(1.0)

    kick = SoccerKickManager(robot)
    kick.start()
    print('mode after start:', robot.get_mode(), flush=True)
    # Aim at the opponent goal centre (+x goal at 7.0 m on the adult-size field is irrelevant
    # here: direction is relative to robot heading; 0 = straight ahead).
    start = time.monotonic()
    peak, prev, first_cmd = 0.0, None, True
    while time.monotonic() - start < a.seconds:
        rr = r1()
        b = latest['w']['ballPosition']
        c, s = math.cos(rr['yaw']), math.sin(rr['yaw'])
        dx, dy = b[0] - rr['position'][0], b[1] - rr['position'][1]
        bx, by = c * dx + s * dy, -s * dx + c * dy
        kick.update_ball(bx, by)
        if first_cmd:
            kick.update_command(direction=yaw - rr['yaw'], power=a.power)
            first_cmd = False
        now = time.monotonic()
        if prev:
            dt = now - prev[0]
            if dt > 0:
                peak = max(peak, math.hypot(b[0] - prev[1][0], b[1] - prev[1][1]) / dt)
        prev = (now, list(b))
        time.sleep(0.05)
    kick.stop()
    time.sleep(3.0)
    b = latest['w']['ballPosition']
    travel = math.hypot(b[0] - ball0[0], b[1] - ball0[1])
    print(json.dumps({'power': a.power, 'dist': a.dist, 'ball_start': [round(v, 2) for v in ball0[:2]],
                      'ball_end': [round(v, 2) for v in b[:2]], 'travel_m': round(travel, 2),
                      'peak_speed_mps': round(peak, 2), 'robot_upDot': r1()['upDot'],
                      'mode_end': robot.get_mode()}), flush=True)
    worker.stdin.write(json.dumps({'command': 'quit'}) + '\n')
    worker.stdin.flush()


if __name__ == '__main__':
    main()
