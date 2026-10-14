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
    p.add_argument('--zero-vel-at', type=float, default=-1, help='send one set_velocity(0,0,0) this many s after kick start')
    p.add_argument('--pre', default='', help="comma list run before start, after entering soccer: off=VisualKick(false), soccer=ChangeMode(kSoccer), wait=sleep 1s")
    p.add_argument('--head-hz', type=float, default=0.0, help='also send RotateHead at this rate during the kick, like our brain does')
    p.add_argument('--ros', action='store_true', help='publish Kick refs as ROS brain/msg/Kick (like our brain) instead of the SDK publisher')
    p.add_argument('--ros-topic', default='/robot1/kick_ball')
    p.add_argument('--stamp', choices=['wall', 'zero', 'old'], default='wall')
    p.add_argument('--dir', type=float, default=None, help='override Kick.dir (SDK sends 0)')
    p.add_argument('--direction', type=float, default=0.0, help='kick yaw relative to start heading, rad (+ = left)')
    p.add_argument('--reset', action='store_true', help='reset robot1 to its start pose first')
    p.add_argument('--robot-name', default='', help="'' on a fresh single-robot container, 'robot1' after attach")
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

    if a.reset:
        worker.stdin.write(json.dumps({'command': 'reset_robot'}) + '\n')
        worker.stdin.flush()
        time.sleep(5.0)
    robot = BoosterRobot(virtual_robot_name=a.robot_name, enable_tf_listener=False, timeout=10.0)
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
    if a.pre:
        from booster_robotics_sdk_python import RobotMode, VisualKickVersion
        robot.loco_client.ChangeMode(RobotMode.kSoccer)
        time.sleep(2.0)
        for step in a.pre.split(','):
            if step == 'off':
                robot.loco_client.VisualKick(False, version=VisualKickVersion.kV2)
            elif step == 'soccer':
                robot.loco_client.ChangeMode(RobotMode.kSoccer)
            elif step == 'wait':
                time.sleep(1.0)
    if a.ros or a.dir is not None or a.stamp != 'wall':
        import rclpy
        from brain.msg import Kick as RosKick
        if not rclpy.ok():
            rclpy.init()
        rnode = rclpy.create_node('kick_probe_ros')
        rpub = rnode.create_publisher(RosKick, a.ros_topic, 10)
        sdk_build = kick._build_kick_msg

        def publish(**kw):
            m = sdk_build(**kw)
            if a.dir is not None:
                m.dir = a.dir
            if a.stamp == 'old':
                m.header.stamp.sec = 1500  # like sim time
            elif a.stamp == 'zero':
                m.header.stamp.sec, m.header.stamp.nanosec = 0, 0
            if not a.ros:
                kick._visual_kick_pub.Write(m)
                return
            r = RosKick()
            r.header.stamp.sec, r.header.stamp.nanosec = m.header.stamp.sec, m.header.stamp.nanosec
            r.x, r.y, r.goal_x, r.goal_y = m.x, m.y, m.goal_x, m.goal_y
            r.power, r.robot_theta_to_field, r.dir = m.power, m.robot_theta_to_field, m.dir
            rpub.publish(r)
        kick._publish_visual_kick = publish
    kick.start()
    print('mode after start:', robot.get_mode(), flush=True)
    # Aim at the opponent goal centre (+x goal at 7.0 m on the adult-size field is irrelevant
    # here: direction is relative to robot heading; 0 = straight ahead).
    start = time.monotonic()
    peak, prev, first_cmd = 0.0, None, True
    next_head = 0.0
    while time.monotonic() - start < a.seconds:
        rr = r1()
        b = latest['w']['ballPosition']
        c, s = math.cos(rr['yaw']), math.sin(rr['yaw'])
        dx, dy = b[0] - rr['position'][0], b[1] - rr['position'][1]
        bx, by = c * dx + s * dy, -s * dx + c * dy
        kick.update_ball(bx, by)
        if a.zero_vel_at >= 0 and time.monotonic() - start >= a.zero_vel_at:
            robot.set_velocity(vx=0.0, vy=0.0, vyaw=0.0)
            a.zero_vel_at = -1
        if a.head_hz > 0:
            while time.monotonic() >= next_head:
                robot.loco_client.RotateHead(0.45, 0.0)
                next_head = (next_head or time.monotonic()) + 1.0 / a.head_hz
        if first_cmd:
            kick.update_command(direction=yaw + a.direction - rr['yaw'], power=a.power)
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
    print(json.dumps({'robot_start': [round(v, 2) for v in r['position'][:2]] + [round(yaw, 2)], 'power': a.power, 'direction': a.direction, 'dist': a.dist, 'ball_start': [round(v, 2) for v in ball0[:2]],
                      'ball_end': [round(v, 2) for v in b[:2]], 'travel_m': round(travel, 2),
                      'peak_speed_mps': round(peak, 2), 'robot_upDot': r1()['upDot'],
                      'mode_end': robot.get_mode()}), flush=True)
    worker.stdin.write(json.dumps({'command': 'quit'}) + '\n')
    worker.stdin.flush()


if __name__ == '__main__':
    main()
