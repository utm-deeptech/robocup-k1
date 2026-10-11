#!/usr/bin/env python3
"""Record estimated robot/ball poses, decisions and visual-kick commands."""
import argparse
import json
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=120)
    args = parser.parse_args()
    import rclpy
    from geometry_msgs.msg import Pose2D, Point
    from std_msgs.msg import String
    from booster_msgs.msg import RpcReqMsg
    rclpy.init()
    node = rclpy.create_node('sim_soccer_observer')
    state = {}

    def robot(msg):
        state['robot_estimate'] = [msg.x, msg.y, msg.theta]

    def ball(msg):
        state['ball_estimate'] = [msg.x, msg.y]

    def decision(msg):
        state['decision'] = msg.data

    def request(msg):
        header = json.loads(msg.header)
        if header.get('api_id') == 2038:
            print(json.dumps({'wall_time': time.time(), 'visual_kick_request':
                              json.loads(msg.body), **state}), flush=True)

    subscriptions = [
        node.create_subscription(Pose2D, '/booster_soccer/robot_pose', robot, 10),
        node.create_subscription(Point, '/booster_soccer/ball_position', ball, 10),
        node.create_subscription(String, '/booster_soccer/player_decision', decision, 10),
        node.create_subscription(RpcReqMsg, '/LocoApiTopicReq', request, 10),
    ]
    try:
        deadline = time.monotonic() + args.seconds
        next_sample = 0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if time.monotonic() >= next_sample:
                print(json.dumps({'wall_time': time.time(), **state}), flush=True)
                next_sample = time.monotonic() + 0.2
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
