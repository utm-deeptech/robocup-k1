#!/usr/bin/env python3
"""Attach an opposing K1 using Booster's live scene-edit API.

Run with the simulator's .venv Python inside the existing container.
The request uses robot4/team 2, but this simulator may renumber it to robot2.
The default referee roster does not follow that renumbering; this is a stationary
defender obstacle, not a verified opposing match participant.
This adds the body and its simulator controls; it does not start a soccer brain.
"""
import argparse
import json
import sys
import time
import uuid

SIM_ROOT = '/usr/local/booster_robot/booster_robocup_sim'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--x', type=float, default=4.5)
    parser.add_argument('--y', type=float, default=0.0)
    args = parser.parse_args()
    sys.path.insert(0, SIM_ROOT)
    import msgpack
    from websockets.sync.client import connect
    from transport.websocket.message_protocol import MessageType, unpack_message
    from core.physics_transport import PhysicsTransportConfig
    from transport.websocket.physics_ws import PhysicsWebSocketClient

    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='add-opponent')
    state = []
    client.subscribe_simulation_state(lambda value: state.append(value))
    client.connect()
    try:
        deadline = time.monotonic() + 10
        while not state and time.monotonic() < deadline:
            time.sleep(0.1)
        if not state:
            raise RuntimeError('No live simulation state; no edit attempted')
        before = set(state[-1].all_robot_names)
        if len(before) > 1:
            print(json.dumps({'stage': 'already_present', 'robots': state[-1].all_robot_names}))
            return
        if not state[-1].scene_policy.edit:
            raise RuntimeError('Current scene disallows editing')
        params = {'asset_key': 'robot_k1', 'template': 'K1', 'name': 'robot4', 'pos': [args.x, args.y, 0.0],
                  'quat': [0.0, 0.0, 0.0, 1.0], 'team': 2,
                  'color': [0.1, 0.25, 0.85, 1.0]}
        with connect('ws://127.0.0.1:8788/', max_size=None) as ws:
            def request(command):
                request_id = 'opponent-' + uuid.uuid4().hex
                ws.send(json.dumps({'type': 'command', 'command': command,
                                    'params': {'op': 'attach_robot', 'params': params,
                                               '_request_id': request_id}}))
                end = time.monotonic() + 60
                while time.monotonic() < end:
                    message = ws.recv(timeout=max(0.1, end - time.monotonic()))
                    if not isinstance(message, bytes):
                        continue
                    kind, payload = unpack_message(message)
                    if kind != MessageType.COMMAND_RESPONSE:
                        continue
                    result = msgpack.unpackb(payload, raw=False)
                    if result.get('request_id') != request_id:
                        continue
                    if result.get('error'):
                        raise RuntimeError(result['error'])
                    return result.get('data') or {}
                raise TimeoutError('No scene-edit response')
            preflight = request('scene_edit_preflight')
            if preflight.get('allowed') is False:
                raise RuntimeError('Attach preflight rejected: ' + json.dumps(preflight))
            print(json.dumps({'stage': 'preflight_passed'}), flush=True)
            request('scene_edit')
        deadline = time.monotonic() + 20
        while not (set(state[-1].all_robot_names) - before) and time.monotonic() < deadline:
            time.sleep(0.1)
        if not (set(state[-1].all_robot_names) - before):
            raise RuntimeError('Edit responded but no additional robot was observed')
        print(json.dumps({'stage': 'opponent_added', 'robots': state[-1].all_robot_names,
                          'position': params['pos'], 'requested_team': 2,
                          'added_names': sorted(set(state[-1].all_robot_names) - before)}), flush=True)
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
