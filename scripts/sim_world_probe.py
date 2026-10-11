#!/usr/bin/env python3
"""Read live robot/ball physics for verification; sends no simulator commands.

Run using the simulator's .venv Python. Uses its installed transport source.
"""
import argparse
import json
import logging
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--sim-root', default='/usr/local/booster_robot/booster_robocup_sim')
    args = parser.parse_args()
    sys.path.insert(0, args.sim_root)
    logging.basicConfig(level=logging.ERROR)
    from core.physics_transport import PhysicsTransportConfig
    from transport.websocket.physics_ws import PhysicsWebSocketClient
    logging.getLogger().setLevel(logging.ERROR)
    latest = []
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='soccer-world-probe')
    client.connect()
    client.subscribe_game_control_world(lambda frame: latest.append(frame))
    try:
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if latest:
                frame = latest[-1]
                latest.clear()
                print(json.dumps({'wall_time': time.time(), 'sim_time': frame.get('time'),
                                  **frame.get('world', {})}), flush=True)
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
