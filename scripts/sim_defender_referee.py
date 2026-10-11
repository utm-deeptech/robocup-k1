#!/usr/bin/env python3
"""Run Booster's official referee with a live physics connection and CLI roster."""
import asyncio
import sys

sys.path.insert(0, '/usr/local/booster_robot/booster_robocup_sim')
from core.physics_transport import PhysicsTransportConfig
from transport.websocket.physics_ws import PhysicsWebSocketClient
from extensions.game_control.service import PythonGameControlService, config_from_args


def main():
    service = PythonGameControlService(config_from_args())
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='defender-referee')
    service.attach_physics_client(client)
    client.connect()
    try:
        return asyncio.run(service.run())
    finally:
        client.disconnect()


if __name__ == '__main__':
    raise SystemExit(main())
