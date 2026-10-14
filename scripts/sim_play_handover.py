#!/usr/bin/env python3
"""Keep the sim striker playing across referee kickoffs. Sim only.

1. Re-send LT+B (autonomous ACTION) after every referee READY/PLAY transition.
   In the local sim an LT+X (CANCEL) reaches the brain about 1 s after each
   kickoff transition, leaving the striker frozen in PLAY.
2. When the referee teleports robot1 (after a goal or an inactivity restart) the
   robot stops responding. If, during PLAY, robot1 neither walks nor turns for
   --stuck-seconds while either the brain keeps sending Move requests or robot1
   sits at the teleport/entrance spot (-5, +-5), where the frozen brain mostly
   sends zero velocity, restart the robot stack and start a NEW match with
   sim_soccer_autonomy.sh --reset-robot (the score resets). Resetting the robot or
   restarting the brain inside the running match did not unfreeze it: the Studio
   referee kept re-placing robot1 at the entrance. That script stops this watcher
   and starts a new one. Ground-truth pose comes
   from scripts/sim_world_probe.py (simulator venv); Move requests from
   /LocoApiTopicReq (api_id 2001).

Source ROS and this repo's install/setup.bash first. Run from the repo root.
"""
import argparse
import collections
import json
import math
from pathlib import Path
import subprocess
import threading
import time

import rclpy
from booster_interface.msg import RemoteControllerState
from booster_msgs.msg import RpcReqMsg
from game_controller_interface.msg import GameControlData

STATE_NAMES = {0: 'INITIAL', 1: 'READY', 2: 'SET', 3: 'PLAY', 4: 'FINISHED'}
PLAY = 3
SIM_PYTHON = '/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python'
SCRIPTS = Path(__file__).resolve().parent
MOVE_API_ID = 2001
ENTRANCE = (-5.0, 5.0)  # referee teleport spot; y may be mirrored


def log(message):
    print(f'{time.strftime("%T")} {message}', flush=True)


def track_robot(history):
    """Append (monotonic time, x, y, yaw) of robot1 from the simulator, restarting the probe if it exits."""
    while True:
        probe = subprocess.Popen([SIM_PYTHON, '-u', str(SCRIPTS / 'sim_world_probe.py'), '--seconds', '1e9'],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in probe.stdout:
            if not line.startswith('{'):
                continue
            robot = next((r for r in json.loads(line).get('robots', []) if r['name'] == 'robot1'), None)
            if robot:
                history.append((time.monotonic(), robot['position'][0], robot['position'][1], robot['yaw']))
        probe.wait()
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=2.0,
                        help='seconds to wait after the transition before pressing LT+B')
    parser.add_argument('--hold', type=float, default=2.0, help='seconds to hold LT+B')
    parser.add_argument('--stuck-seconds', type=float, default=10.0,
                        help='PLAY time without robot1 movement before reset-and-resume')
    parser.add_argument('--stuck-distance', type=float, default=0.15, help='metres counted as movement')
    parser.add_argument('--stuck-turn', type=float, default=0.3, help='radians counted as movement')
    parser.add_argument('--no-recovery', action='store_true', help='only re-send LT+B')
    args = parser.parse_args()

    rclpy.init()
    node = rclpy.create_node('sim_play_handover')
    publisher = node.create_publisher(RemoteControllerState, '/remote_controller_state', 10)
    game = {'state': None}
    pending = [None]  # monotonic time at which to press LT+B
    quiet_until = [0.0]  # no stuck checks before this (after LT+B or a recovery)
    history = collections.deque(maxlen=200)
    moves = collections.deque(maxlen=2000)  # (monotonic time, brain asked to move)

    def on_game(msg):
        if msg.state != game['state']:
            game['state'] = msg.state
            if msg.state in (1, PLAY):
                pending[0] = time.monotonic() + args.delay
                # no stuck checks until LT+B is sent (it moves quiet_until forward then)
                quiet_until[0] = float('inf')
                log(f'{STATE_NAMES.get(msg.state, msg.state)}: LT+B in {args.delay:.1f}s')

    def on_loco(msg):
        try:
            if json.loads(msg.header).get('api_id') != MOVE_API_ID:
                return
            body = json.loads(msg.body)
        except (ValueError, AttributeError):
            return
        active = abs(body.get('vx', 0)) + abs(body.get('vy', 0)) > 0.1 or abs(body.get('vyaw', 0)) > 0.3
        moves.append((time.monotonic(), active))

    def robot_stuck():
        # only movement after the last LT+B / recovery counts, over a full window
        now = time.monotonic()
        if game['state'] != PLAY or now < quiet_until[0] + args.stuck_seconds or not history:
            return False
        window = [(x, y, yaw) for t, x, y, yaw in history if t >= now - args.stuck_seconds]
        asked = [active for t, active in moves if t >= now - args.stuck_seconds]
        if now - history[-1][0] > 2 or len(window) < 2:
            return False
        x0, y0, yaw0 = window[0]
        at_entrance = math.hypot(x0 - ENTRANCE[0], abs(y0) - ENTRANCE[1]) < 0.6
        if not at_entrance and sum(asked) < 0.7 * len(asked):  # standing still on purpose
            return False
        return all(math.hypot(x - x0, y - y0) < args.stuck_distance
                   and abs(math.remainder(yaw - yaw0, math.tau)) < args.stuck_turn
                   for x, y, yaw in window)

    def recover():
        log('robot1 stuck in PLAY: restarting robot stack and starting a new match')
        with open(SCRIPTS.parent / 'sim_play_recovery.log', 'a') as out:
            subprocess.Popen(['setsid', 'bash', str(SCRIPTS / 'sim_soccer_autonomy.sh'),
                              '--reset-robot'],
                             cwd=SCRIPTS.parent, stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        quiet_until[0] = float('inf')  # the restart replaces this watcher

    if not args.no_recovery:
        threading.Thread(target=track_robot, args=(history,), daemon=True).start()
    node.create_subscription(GameControlData, '/robocup/game_controller', on_game, 10)
    if not args.no_recovery:
        node.create_subscription(RpcReqMsg, '/LocoApiTopicReq', on_loco, 50)
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
        if pending[0] is not None and time.monotonic() >= pending[0]:
            pending[0] = None
            deadline = time.monotonic() + args.hold
            while time.monotonic() < deadline:
                publisher.publish(RemoteControllerState(lt=True, b=True))
                rclpy.spin_once(node, timeout_sec=0.1)
            publisher.publish(RemoteControllerState())
            quiet_until[0] = time.monotonic()
            log('LT+B sent')
        elif not args.no_recovery and robot_stuck():
            recover()


if __name__ == '__main__':
    main()
