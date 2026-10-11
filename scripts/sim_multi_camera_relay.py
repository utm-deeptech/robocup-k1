#!/usr/bin/env python3
"""Publish native render model/state for an existing multi-robot simulation.

Run using the simulator .venv inside the existing container. This relay reads
its exported scene snapshot and live physics states. It runs no physics and
accepts no forwarded control commands. Installed simulator files stay intact.
"""
import argparse
from pathlib import Path
import sys
import threading
import time

SIM_ROOT = '/usr/local/booster_robot/booster_robocup_sim'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8790)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--stale-seconds', type=float, default=20,
                        help='Allow brief physics pauses during robot controller resets')
    args = parser.parse_args()
    if args.fps <= 0 or args.stale_seconds <= 0:
        parser.error('fps and stale-seconds must be positive')
    sys.path.insert(0, SIM_ROOT)
    from core.mujoco_model_cache import acquire_scene
    from core.model_colors import apply_color_markers
    from core.model_visibility import apply_hidden_collision_geom_visibility
    import mujoco
    from core.physics_transport import PhysicsTransportConfig
    from transport.websocket.physics_ws import PhysicsWebSocketClient, PhysicsWebSocketServer
    from robot.model_detection import detect_robot_instances

    lock = threading.Lock()
    latest = {}
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='multi-camera-relay')

    def receive(key, value):
        with lock:
            latest[key] = (value, time.monotonic())

    client.subscribe_simulation_state(lambda value: receive('simulation', value))
    client.subscribe_physics_state(lambda value: receive('physics', value))
    client.connect()
    server = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with lock:
                ready = 'simulation' in latest and 'physics' in latest
            if ready:
                break
            time.sleep(0.1)
        if not ready:
            raise RuntimeError('Missing live simulator state')
        state = latest['simulation'][0]
        revision = state.model_revision
        snapshot = Path('/tmp/booster-runtime-scenes') / (revision + '.mjspec.zip')
        if not snapshot.is_file():
            raise RuntimeError('Exported scene snapshot unavailable: ' + str(snapshot))
        model = acquire_scene(str(snapshot), owner='multi-camera-relay').model
        # Match the installed physics process's render-model preparation.
        apply_hidden_collision_geom_visibility(model)
        apply_color_markers(model)
        names = [robot.name for robot in detect_robot_instances(model)]
        if names != state.all_robot_names:
            raise RuntimeError('Snapshot robot topology differs from live simulation')
        cameras = client.request_visual_scene(profile='camera_metadata')['scene']['cameras']
        data = mujoco.MjData(model)
        server = PhysicsWebSocketServer(PhysicsTransportConfig(host='0.0.0.0', port=args.port))
        server.start()
        server.update_render_model(model, revision, cameras)
        print(f'Relay ready: robots={names}, nq={model.nq}, cameras={len(cameras)}, port={args.port}', flush=True)
        frames = 0
        last_report = time.monotonic()
        while True:
            started = time.monotonic()
            with lock:
                simulation = latest['simulation'][0]
                physics, received_at = latest['physics']
            if simulation.model_revision != revision:
                raise RuntimeError('Scene topology changed; restart relay against new snapshot')
            if started - received_at > args.stale_seconds:
                raise RuntimeError('Live physics stream stalled')
            if (len(physics.qpos), len(physics.qvel), len(physics.ctrl)) != (model.nq, model.nv, model.nu):
                raise RuntimeError('Snapshot state dimensions differ from live physics')
            data.qpos[:] = physics.qpos
            data.qvel[:] = physics.qvel
            data.ctrl[:] = physics.ctrl
            data.time = physics.time
            server.publish_render_state(model, data, revision, physics.frame_id)
            frames += 1
            if started - last_report >= 10:
                print(f'Relay live: frames={frames}, sim_time={physics.time:.3f}', flush=True)
                last_report = started
            time.sleep(max(0, 1 / args.fps - (time.monotonic() - started)))
    finally:
        if server is not None:
            server.stop()
        client.disconnect()


if __name__ == '__main__':
    main()
