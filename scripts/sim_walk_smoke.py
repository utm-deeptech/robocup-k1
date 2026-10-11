#!/usr/bin/env python3
"""SDK smoke test, run inside the virtual robot after sourcing ROS Humble.

API usage follows installed python_example/sdk_pybind_b1_example.py (SDK 1.5.6).
Uses simulator ground truth, wall-clock timeouts, and stops on every exit.
"""
import argparse
import json
import math
import time

import booster_robotics_sdk_python as sdk
import rclpy
from geometry_msgs.msg import Pose2D
from rclpy.qos import qos_profile_sensor_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='lo',
                        help='Booster virtual robot DDS uses loopback')
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('sim_walk_smoke')
    latest = []

    def receive(msg):
        latest[:] = [(msg.x, msg.y, msg.theta), time.monotonic()]

    subscription = node.create_subscription(
        Pose2D, '/soccer/sim/localization/robot_pose', receive,
        qos_profile_sensor_data)

    def pose():
        rclpy.spin_once(node, timeout_sec=0.05)
        if not latest or time.monotonic() - latest[1] > 1:
            raise RuntimeError('Missing or stale simulator pose')
        return latest[0]

    def settle(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            rclpy.spin_once(node, timeout_sec=0.05)

    def emit(label):
        value = pose()
        print(json.dumps({'stage': label, 'x': value[0], 'y': value[1],
                          'theta': value[2]}), flush=True)
        return value

    def drive(velocity, completed, timeout):
        deadline = time.monotonic() + timeout
        while not completed(pose()):
            if time.monotonic() >= deadline:
                raise RuntimeError('Motion deadline exceeded')
            client.Move(*velocity)
            settle(0.05)
        client.Move(0, 0, 0)
        settle(1)

    sdk.ChannelFactory.Instance().Init(0, args.interface)
    client = sdk.B1LocoClient()
    client.Init()
    try:
        settle(2)
        emit('before')
        client.ChangeMode(sdk.RobotMode.kPrepare)
        settle(3)
        client.ChangeMode(sdk.RobotMode.kWalking)
        settle(3)
        mode = client.GetMode().mode
        print('Walking mode:', mode, flush=True)
        if mode != sdk.RobotMode.kWalking:
            raise RuntimeError('Robot did not enter walking mode')
        start = emit('walk_start')
        drive((0.3, 0, 0),
              lambda p: math.hypot(p[0]-start[0], p[1]-start[1]) >= 1, 30)
        turn_start = emit('after_forward')
        def turned(p):
            angle = math.atan2(math.sin(p[2]-turn_start[2]),
                               math.cos(p[2]-turn_start[2]))
            return angle >= math.pi / 2
        drive((0, 0, 0.4), turned, 20)
        emit('after_turn')
    finally:
        try:
            client.Move(0, 0, 0)
            settle(2)
            emit('stopped')
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
