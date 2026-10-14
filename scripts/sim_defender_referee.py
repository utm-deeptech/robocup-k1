#!/usr/bin/env python3
"""Run Booster's official referee with a live physics connection and CLI roster."""
import asyncio
import os
import sys

sys.path.insert(0, '/usr/local/booster_robot/booster_robocup_sim')
from core.physics_transport import PhysicsTransportConfig
from transport.websocket.physics_ws import PhysicsWebSocketClient
from extensions.game_control.service import PythonGameControlService, config_from_args


def also_publish_json(publisher, topic):
    """Send each UDP broadcast as Booster's JSON topic too, so the official
    default AI (JSON) and our game_controller node (UDP) can share one referee.
    Test fixture only: uses Booster's own serializer; referee logic unchanged."""
    from extensions.game_control.publishing.game_control import (
        RosStringPublisher, serialize_control_message_json)
    json_publisher = RosStringPublisher(topic)
    udp_broadcast_once = publisher.broadcast_once

    def broadcast_once():
        udp_broadcast_once()
        if publisher.latest_publication:
            json_publisher.publish(serialize_control_message_json(publisher.latest_publication['controlMessage']))

    publisher.broadcast_once = broadcast_once


def main():
    service = PythonGameControlService(config_from_args())
    if os.environ.get('SIM_REFEREE_ALSO_JSON') == '1':
        also_publish_json(service.game_control_publisher, service.config.json_topic)
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='defender-referee')
    service.attach_physics_client(client)
    client.connect()
    try:
        return asyncio.run(service.run())
    finally:
        client.disconnect()


if __name__ == '__main__':
    raise SystemExit(main())
