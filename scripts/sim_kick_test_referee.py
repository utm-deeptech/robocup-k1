#!/usr/bin/env python3
"""Test fixture using the official referee with open-play shot trials.

The normal READY/SET/PLAY sequence runs. On its first PLAY frame, end kickoff
restrictions using the official controller's finish_set_play method. Disable
automatic ball placement and inactivity restarts for the trial. Goal/out rules,
the wire protocol, and team rosters remain the official implementation.
This is local measurement infrastructure, never a submitted agent dependency.
"""
import asyncio
import sys

sys.path.insert(0, '/usr/local/booster_robot/booster_robocup_sim')
from core.physics_transport import PhysicsTransportConfig
from transport.websocket.physics_ws import PhysicsWebSocketClient
from extensions.game_control.service import PythonGameControlService, config_from_args


class KickTestReferee(PythonGameControlService):
    def __init__(self, config):
        self.open_play_pending = False
        super().__init__(config)

    def _start_match(self):
        with self._state_lock:
            result = super()._start_match()
            self.rules.set_automatic_options({'place_ball': False,
                                             'handle_global_game_stuck': False,
                                             'clear_stuck_ball': False,
                                             'penalize_stopped_motion': False})
            self.open_play_pending = True
            return result

    def observe_game_control_world(self, frame):
        super().observe_game_control_world(frame)
        with self._state_lock:
            before = self.controller.snapshot
            if self.open_play_pending and before['state'] == 'playing':
                self.controller.finish_set_play()
                self.rules.reset()
                self.open_play_pending = False
                self._observe_state_change(before, self.controller.snapshot,
                                           source='kick_test_fixture', reason='open_play_trial')
                self.controller.maybe_publish()
                print('Kick test fixture: open play, no automatic ball placement/inactivity restart', flush=True)


def main():
    service = KickTestReferee(config_from_args())
    client = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='kick-test-referee')
    service.attach_physics_client(client)
    client.connect()
    try:
        return asyncio.run(service.run())
    finally:
        client.disconnect()


if __name__ == '__main__':
    raise SystemExit(main())
