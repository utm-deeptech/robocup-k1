"""PLAY-stage subtree factory; a complete playbook map for newcomers.

Shape:

Sequence(PlayingPhase)
|-- IsGameInState(PLAYING)
`-- Roles (Parallel)
    |-- Player(1) selector
    |   |-- PersonalAvoid(1)
    |   |-- PersonalStopped(1)
    |   `-- WaitForBall(1) fallback
    |-- Player(2) ...
    `-- Player(3) ...

Each ``As<role.name>`` branch is an :class:`IsRole` check plus the subtree
returned by ``role.build_subtree(build)``. Player Selector branch order follows
``playbook.role_registry`` registration order: chaser, supporter, then
goalkeeper by default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import py_trees

from ..soccer_framework import GameState
from ..behavior_tree.nodes.actions import (
    AvoidOpponentRestart,
    GoReadyTarget,
    StopPlayer,
)
from ..behavior_tree.nodes.conditions import (
    IsGameInState,
    IsGameStopped,
    IsOpponentKickoffActive,
    IsOpponentRestartActive,
)
from .nodes import AssignRoles, IsRole, WaitForBall
from .playbook import Playbook

if TYPE_CHECKING:
    from ..runtime import SoccerKit


def _create_role_subtree(
    kit: "SoccerKit",
    playbook: Playbook,
    player_id: int,
) -> py_trees.behaviour.Behaviour:
    """Per-player subtree that selects a branch by dynamic role.

    Branch order equals ``playbook.role_registry`` registration order, with WaitForBall as the final fallback.
    """

    branches: list[py_trees.behaviour.Behaviour] = []

    kickoff_hold = py_trees.composites.Sequence(
        name=f"KickoffHold({player_id})",
        memory=False,
        children=[
            IsOpponentKickoffActive(kit),
            GoReadyTarget(kit, player_id),
        ],
    )
    branches.append(kickoff_hold)

    # Personal avoidance guard during opponent set plays.
    personal_avoid_guard = py_trees.composites.Sequence(
        name=f"PenaltyAvoid({player_id})",
        memory=False,
        children=[
            IsOpponentRestartActive(kit),
            AvoidOpponentRestart(kit, player_id),
        ],
    )
    branches.append(personal_avoid_guard)

    # Personal stop guard while the referee pauses ball placement, preventing stopped=True motion penalties.
    personal_stopped_guard = py_trees.composites.Sequence(
        name=f"PenaltyStopped({player_id})",
        memory=False,
        children=[
            IsGameStopped(),
            StopPlayer(kit, player_id, "game stopped"),
        ],
    )
    branches.append(personal_stopped_guard)

    # Normal role-tactic execution branches.
    for role in playbook.role_registry:
        branches.append(
            py_trees.composites.Sequence(
                name=f"As{role.name.capitalize()}({player_id})",
                memory=False,
                children=[
                    IsRole(player_id, role.name),
                    role.build_subtree(kit, player_id),
                ],
            )
        )
    branches.append(WaitForBall(kit, playbook, player_id))

    return py_trees.composites.Selector(
        name=f"Player({player_id})",
        memory=False,
        children=branches,
    )


def create_play_subtree(
    kit: "SoccerKit",
    playbook: Playbook,
) -> py_trees.behaviour.Behaviour:
    """PLAY subtree: assign roles by Playbook, run players in parallel, and let each player handle top-level avoidance and stopping."""

    role_branches = py_trees.composites.Parallel(
        name="Roles",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False),
        children=[
            _create_role_subtree(kit, playbook, player_id)
            for player_id in kit.config.player_ids
        ],
    )
    playbook_core = py_trees.composites.Sequence(
        name="PlaybookCore",
        memory=False,
        children=[
            # Do not gate IsBallKnown here; when the ball is lost, the Roles subtree must still run.
            # AssignRoles returns an empty RoleAssignment when the ball is missing, so each Player falls through
            # to WaitForBall with an explicit reason instead of letting role branches idle.
            AssignRoles(playbook),
            role_branches,
        ],
    )

    return py_trees.composites.Sequence(
        name="PlayingPhase",
        memory=False,
        children=[IsGameInState(GameState.PLAYING), playbook_core],
    )
