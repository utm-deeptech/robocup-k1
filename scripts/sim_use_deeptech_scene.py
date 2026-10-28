#!/usr/bin/env python3
"""(Re)load our deeptech_pitch_K1 scene in the live simulator (robot1 in DeepTech navy, robot2
opponent). Always reloads, so every match starts clean and scene-file edits take effect.
Build the scene first with make_deeptech_scene.py.

Run with the simulator's .venv Python inside the container. Uses Booster's own switch_scene
command; nothing in Booster's simulator or referee is changed.
"""
import json
import sys
import time
import uuid
import logging

SIM_ROOT = '/usr/local/booster_robot/booster_robocup_sim'
SCENE_KEY = 'deeptech_pitch_K1'


def main():
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, SIM_ROOT)
    from websockets.sync.client import connect
    from core.physics_transport import PhysicsTransportConfig
    from transport.websocket.physics_ws import PhysicsWebSocketClient

    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='deeptech-scene')
    state = []
    client.subscribe_simulation_state(lambda value: state.append(value))
    client.connect()

    def wait(pred, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if state and pred(state[-1]):
                return True
            time.sleep(0.2)
        return False

    try:
        if not wait(lambda s: True, 10):
            raise RuntimeError('No live simulation state')
        if True:  # always reload: clean start, and picks up an edited scene file
            previous = state[-1].scene_key
            with connect('ws://127.0.0.1:8788/', max_size=None) as ws:
                ws.send(json.dumps({'type': 'command', 'command': 'switch_scene',
                                    'params': {'scene_key': SCENE_KEY,
                                               '_request_id': 'deeptech-' + uuid.uuid4().hex}}))
            client.disconnect()
            client.connect()  # the physics server restarts its loop on a scene switch
            state.clear()
            if not wait(lambda s: s.scene_key == SCENE_KEY and s.runtime_scene_ready
                        and len(s.all_robot_names or []) == 2, 180):
                raise RuntimeError(f'switch from {previous} to {SCENE_KEY} not observed')
        s = state[-1]
        print(json.dumps({'stage': 'scene_ready', 'scene': s.scene_key, 'robots': s.all_robot_names}),
              flush=True)
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
