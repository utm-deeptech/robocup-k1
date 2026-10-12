#!/usr/bin/env python3
"""Initialize official demo localization and referee handover inside the simulator.

Source ROS and this repo's install/setup.bash first. Start sim_start.sh first.
--reset-robot returns robot1 to its starting pose using the simulator's API.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-robot', action='store_true')
    parser.add_argument('--localization-timeout', type=float, default=60)
    parser.add_argument('--resume', action='store_true',
                        help='Re-enter soccer mode and relocalize after a simulator reset; keep the running match')
    args = parser.parse_args()
    import booster_robotics_sdk_python as sdk
    import rclpy
    from booster_interface.msg import RemoteControllerState

    if args.reset_robot:
        sim_root = '/usr/local/booster_robot/booster_robocup_sim'
        subprocess.run([sim_root + '/.venv/bin/python', '-c', '''
import time
from core.physics_transport import PhysicsTransportConfig, PhysicsCommand
from transport.websocket.physics_ws import PhysicsWebSocketClient
c = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='soccer-initialize')
world = []
c.subscribe_game_control_world(lambda frame: world.append(frame))
c.connect()
time.sleep(1)
if not world:
    raise RuntimeError('No live world; reset was not attempted')
robot = next(r for r in world[-1]['world']['robots'] if r['name'] == 'robot1')
# Release any referee penalty hold before resetting the motion controller.
c.send_command(PhysicsCommand.SET_BODY_POSITION,
               {'body_id': robot['bodyId'], 'is_dragging': False, 'zero_velocity': True})
c.send_command(PhysicsCommand.RESET_ROBOT, {'robot_name': 'robot1'})
time.sleep(3)
c.disconnect()
'''], cwd=sim_root, check=True, timeout=15)

    sdk.ChannelFactory.Instance().Init(0, 'lo')
    client = sdk.B1LocoClient()
    client.Init()
    client.ChangeMode(sdk.RobotMode.kSoccer)
    time.sleep(2)
    rclpy.init()
    node = rclpy.create_node('sim_match_initializer')
    publisher = node.create_publisher(RemoteControllerState, '/remote_controller_state', 10)
    success = False

    def buttons(**fields):
        message = RemoteControllerState(**fields)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            publisher.publish(message)
            rclpy.spin_once(node, timeout_sec=0.1)
        publisher.publish(RemoteControllerState())
        rclpy.spin_once(node, timeout_sec=0.2)

    try:
        log = Path('brain.log')
        offset = log.stat().st_size
        buttons(lt=True, a=True)
        deadline = time.monotonic() + args.localization_timeout
        localized = ''
        with log.open() as stream:
            stream.seek(offset)
            while time.monotonic() < deadline:
                for line in stream.readlines():
                    if 'Locate Success:' in line:
                        localized = line.strip()
                if localized:
                    break
                rclpy.spin_once(node, timeout_sec=0.2)
        if not localized:
            raise RuntimeError('Localization did not succeed; match was not started')
        print(json.dumps({'stage': 'localized', 'evidence': localized}), flush=True)
        buttons(lt=True, b=True)
        if args.resume:
            success = True
            print(json.dumps({'stage': 'resumed'}), flush=True)
            return
        request = urllib.request.Request('http://127.0.0.1:38383/match/start',
                                         data=b'', method='POST')
        result = json.load(urllib.request.urlopen(request, timeout=5))
        if not result.get('ok'):
            raise RuntimeError('Referee rejected match start')
        success = True
        print(json.dumps({'stage': 'match_started', 'state': result['game']['state']}), flush=True)
    finally:
        try:
            if not success:
                buttons(lt=True, x=True)
                client.Move(0, 0, 0)
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
