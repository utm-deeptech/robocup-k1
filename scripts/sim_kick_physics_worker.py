#!/usr/bin/env python3
"""Test-only physics observer/placement worker; run with the simulator venv.

JSON lines on stdin accept reset_robot, place_ball, and quit. JSON lines on
stdout contain live world frames. No truth is published into agent topics.
"""
import json
import logging
import sys
import threading
import time

SIM_ROOT = '/usr/local/booster_robot/booster_robocup_sim'


def main():
    sys.path.insert(0, SIM_ROOT)
    logging.basicConfig(level=logging.ERROR)
    from core.physics_transport import PhysicsTransportConfig, PhysicsCommand
    from transport.websocket.physics_ws import PhysicsWebSocketClient
    logging.getLogger().setLevel(logging.ERROR)
    lock = threading.Lock()
    latest = {}
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='kick-baseline-observer')

    def world(frame):
        latest['frame'] = frame
        with lock:
            print(json.dumps({'kind': 'world', 'wall_time': time.time(), **frame}), flush=True)

    client.subscribe_game_control_world(world)
    client.connect()
    try:
        deadline = time.monotonic() + 10
        while not latest and time.monotonic() < deadline:
            time.sleep(0.05)
        if not latest:
            raise RuntimeError('No physics ground truth')
        for line in sys.stdin:
            request = json.loads(line)
            command = request['command']
            frame = latest['frame']['world']
            if command == 'quit':
                break
            if command == 'reset_robot':
                robot = next(r for r in frame['robots'] if r['name'] == 'robot1')
                client.send_command(PhysicsCommand.SET_BODY_POSITION,
                                    {'body_id': robot['bodyId'], 'is_dragging': False, 'zero_velocity': True})
                client.send_command(PhysicsCommand.RESET_ROBOT, {'robot_name': 'robot1'})
            elif command == 'place_ball':
                client.send_command(PhysicsCommand.SET_BODY_POSITION,
                                    {'body_id': frame['ballBodyId'], 'position': request['position'],
                                     'is_dragging': False, 'zero_velocity': True})
            else:
                raise ValueError('Unsupported test command: ' + command)
            with lock:
                print(json.dumps({'kind': 'command_sent', 'wall_time': time.time(), **request}), flush=True)
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
