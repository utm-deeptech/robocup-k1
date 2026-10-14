#!/usr/bin/env python3
"""Run our team (agents/k1team) without Booster's agent manager, for local matches.

Booster's supervisor allows one agent per container (shared lock + agent manager); the
official runner gives each team its own sandbox. Locally we run Booster's AI through the
supervisor and ours directly through the same SoccerTeamRuntime the AgentBase entry uses.
Env: SOCCER_TEAM_ID, SOCCER_ROBOT_NAMES, SOCCER_OPPONENT_ROBOT_NAMES (as the supervisor sets).
"""
import logging
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents' / 'k1team'))
sys.path.insert(1, '/opt/booster/booster_agent_data/data/agents/extract/com.k1team.soccer/libs/python-x86_64')

import rclpy  # noqa: E402

from com_booster_default3v3ai.runtime import SoccerTeamRuntime  # noqa: E402
from com_booster_default3v3ai.soccer_framework import SoccerConfig  # noqa: E402
from com_booster_default3v3ai.soccer_framework.telemetry import create_soccer_logger  # noqa: E402


class _Logger:
    """Minimal stand-in for the AgentBase logger (info/warn/error/debug)."""

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
        self._log = logging.getLogger('k1team')

    def info(self, msg, *a, **k): self._log.info(msg)
    def warn(self, msg, *a, **k): self._log.warning(msg)
    warning = warn
    def error(self, msg, *a, **k): self._log.error(msg)
    def debug(self, msg, *a, **k): self._log.debug(msg)


def main():
    if not rclpy.ok():
        rclpy.init()
    config = SoccerConfig.from_env()
    logger = create_soccer_logger(_Logger(), source=f'k1team.team{config.team_id}')
    runtime = SoccerTeamRuntime(logger=logger, config=config)
    done = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: done.set())
    runtime.start()
    print(f'k1team runtime started team={config.team_id} robots={list(config.robot_names)}', flush=True)
    done.wait()
    runtime.stop()


if __name__ == '__main__':
    main()
