#!/usr/bin/env python3
"""Measure robot1's real walking speed and falls at each commanded forward speed (test only).

Per run: reset robot1 to its spawn (outside the sideline, facing into the field), enter the
soccer gait our agent uses, command vx for --seconds, and track simulator truth.
Run in the container with ROS sourced, agents stopped, referee running (for truth frames):
  python3 scripts/sim_walk_speed_test.py --speeds 0.8 1.0 1.2 --repeats 4
"""
import argparse
import json
import math
import time

from sim_kick_power_test import World, wait_for


def run(world, robot, vx, seconds):
    world.command('reset_robot')
    time.sleep(3.0)
    robot.set_gait('soccer')
    robot.set_mode('walk')
    time.sleep(1.0)
    x0, y0, _ = world.robot1()
    t0 = time.monotonic()
    fell, min_up, path = False, 1.0, []
    try:
        while time.monotonic() - t0 < seconds:
            robot.set_velocity(vx=vx, vy=0.0, vyaw=0.0)
            with world.lock:
                up = next(r for r in world.frame['robots'] if r['name'] == 'robot1').get('upDot', 1.0)
            min_up = min(min_up, up)
            if up < 0.5:
                fell = True
                break
            path.append((time.monotonic(), *world.robot1()[:2]))
            time.sleep(0.05)
    finally:
        try:
            robot.set_velocity(vx=0.0, vy=0.0, vyaw=0.0)
        except RuntimeError:
            pass
    # steady-state speed over the second half of the run (wall clock -> scaled later)
    half = [p for p in path if p[0] >= path[0][0] + (path[-1][0] - path[0][0]) / 2] if path else []
    wall_speed = (math.dist(half[0][1:], half[-1][1:]) / (half[-1][0] - half[0][0])
                  if len(half) > 2 and half[-1][0] > half[0][0] else 0.0)
    return {'cmd_vx': vx, 'fell': fell, 'min_upDot': round(min_up, 2),
            'distance_m': round(math.dist((x0, y0), path[-1][1:]), 2) if path else 0.0,
            'wall_speed': round(wall_speed, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speeds', type=float, nargs='+', default=[0.8, 1.0, 1.2])
    parser.add_argument('--repeats', type=int, default=4)
    parser.add_argument('--seconds', type=float, default=8.0)
    args = parser.parse_args()

    from boosteros.robots.booster import BoosterRobot
    world = World()
    robot = BoosterRobot(virtual_robot_name='robot1', enable_tf_listener=False, timeout=10.0)
    try:
        if not wait_for(lambda: world.frame is not None, 15):
            raise RuntimeError('no simulator truth (is the referee running?)')
        for repeat in range(args.repeats):
            for vx in args.speeds:
                try:
                    result = run(world, robot, vx, args.seconds)
                except RuntimeError as exc:
                    result = {'cmd_vx': vx, 'error': str(exc)}
                print(json.dumps({'repeat': repeat, **result}), flush=True)
    finally:
        world.close()


if __name__ == '__main__':
    main()
