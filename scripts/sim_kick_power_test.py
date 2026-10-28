#!/usr/bin/env python3
"""Measure how far robot1's kick sends the ball at each kick power (test only, no match).

Uses the same boosteros SoccerKickManager call our agent makes (direction + power in
[1, 10]). Per trial: reset robot1 to its spawn, place the ball at BALL_START, kick toward
+x (the long axis), and track the ball with simulator truth until it stops.
Run in the container with ROS sourced, after stopping agents and the referee:
  python3 scripts/sim_kick_power_test.py --powers 1.5 3 5 7 10 --repeats 2
"""
import argparse
import json
import math
import subprocess
import threading
import time

SIM_PYTHON = '/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python'
WORKER = '/root/robocup_demo/scripts/sim_kick_physics_worker.py'
BALL_START = (-4.5, 3.0)
KICK_HEADING = 0.0  # world yaw: +x, toward the far end line at x = 7


class World:
    """Simulator truth from the physics worker (ball and robot1 pose)."""

    def __init__(self):
        self.proc = subprocess.Popen([SIM_PYTHON, WORKER], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, bufsize=1)
        self.frame = None
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get('kind') == 'world':
                with self.lock:
                    self.frame = msg['world']

    def command(self, command, **kwargs):
        self.proc.stdin.write(json.dumps({'command': command, **kwargs}) + '\n')
        self.proc.stdin.flush()

    def ball(self):
        with self.lock:
            return list(self.frame['ballPosition']) if self.frame else None

    def robot1(self):
        """(x, y, yaw) of robot1 from simulator truth."""
        with self.lock:
            robot = next(r for r in self.frame['robots'] if r['name'] == 'robot1')
        x, y = robot['position'][:2]
        if 'yaw' in robot:
            return x, y, robot['yaw']
        w, qx, qy, qz = robot['quaternion']
        return x, y, math.atan2(2 * (w * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

    def close(self):
        try:
            self.command('quit')
        except (BrokenPipeError, OSError):
            pass
        self.proc.terminate()


def wait_for(predicate, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def trial(world, robot, kicker, power, timeout):
    world.command('reset_robot')
    time.sleep(3.0)
    robot.set_gait('soccer')
    robot.set_mode('walk')
    world.command('place_ball', position=[*BALL_START, 0.11])
    if not wait_for(lambda: math.dist(world.ball()[:2], BALL_START) < 0.05, 5):
        return {'power': power, 'error': 'ball placement failed'}
    time.sleep(0.5)
    start = world.ball()[:2]
    kicker.start()
    t0, kicked_at, path = time.monotonic(), None, []
    try:
        while time.monotonic() - t0 < timeout:
            rx, ry, ryaw = world.robot1()
            bx, by = world.ball()[:2]
            dx, dy = bx - rx, by - ry
            if kicked_at is None:  # re-aim every tick like our agent does
                kicker.update_command(direction=math.remainder(KICK_HEADING - ryaw, math.tau), power=power)
            kicker.update_ball(x=math.cos(ryaw) * dx + math.sin(ryaw) * dy,
                               y=-math.sin(ryaw) * dx + math.cos(ryaw) * dy)
            if kicked_at is None and math.dist((bx, by), start) > 0.3:
                kicked_at = time.monotonic()
                kicker.stop()
                robot.set_velocity(vx=0.0, vy=0.0, vyaw=0.0)
            if kicked_at is not None:
                path.append((time.monotonic(), bx, by))
                recent = [p for p in path if p[0] > path[-1][0] - 1.0]
                if (path[-1][0] - kicked_at > 1.5
                        and math.dist(recent[0][1:], recent[-1][1:]) < 0.03):
                    break
            time.sleep(0.05)
    finally:
        for cleanup in (kicker.stop, lambda: robot.set_velocity(vx=0.0, vy=0.0, vyaw=0.0)):
            try:
                cleanup()
            except RuntimeError:  # robot fell or left soccer mode; reset_robot recovers it
                pass
    if kicked_at is None:
        return {'power': power, 'error': 'no kick within %.0fs' % timeout}
    end = path[-1][1:]
    travel = math.dist(start, end)
    along = (end[0] - start[0]) * math.cos(KICK_HEADING) + (end[1] - start[1]) * math.sin(KICK_HEADING)
    side = -(end[0] - start[0]) * math.sin(KICK_HEADING) + (end[1] - start[1]) * math.cos(KICK_HEADING)
    return {'power': power, 'travel_m': round(travel, 2), 'forward_m': round(along, 2),
            'sideways_m': round(side, 2), 'angle_err_deg': round(math.degrees(math.atan2(side, along)), 1),
            'end': [round(end[0], 2), round(end[1], 2)],
            'out': abs(end[0]) > 7.0 or abs(end[1]) > 4.5,
            'walk_to_kick_s': round(kicked_at - t0, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--powers', type=float, nargs='+', default=[1.5, 3, 5, 7, 10])
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=60.0)
    args = parser.parse_args()

    from boosteros.robots.booster import BoosterRobot, SoccerKickManager
    world = World()
    robot = BoosterRobot(virtual_robot_name='robot1', enable_tf_listener=False, timeout=10.0)
    kicker = SoccerKickManager(robot)
    try:
        if not wait_for(lambda: world.frame is not None, 15):
            raise RuntimeError('no simulator truth')
        for repeat in range(args.repeats):
            for power in args.powers:
                try:
                    result = trial(world, robot, kicker, power, args.timeout)
                except RuntimeError as exc:
                    result = {'power': power, 'error': str(exc)}
                print(json.dumps({'repeat': repeat, **result}), flush=True)
    finally:
        world.close()


if __name__ == '__main__':
    main()
