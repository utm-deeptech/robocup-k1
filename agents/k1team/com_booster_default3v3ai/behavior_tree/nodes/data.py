"""Data-layer leaves that write external inputs and shared state to the blackboard each tick.

``UpdateGameState``
The tree root chains these nodes in a ``Sequence`` because they depend on each other:
``UpdateClock`` writes time, ``UpdatePlayContext`` reads callbacks, freshness filters run,
and ``UpdateRobotStatus`` pulls hardware status.

PLAY-stage role assignment used to live here (old ``UpdateChaser``), but now
belongs to :class:`src.play.nodes.AssignRoles` so it only runs when play actually starts.

To add a new global input, add a ``_DataLeaf`` subclass and mount it in the DataLayer ``Sequence``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import py_trees

from ...soccer_framework import RobotRuntimeStatus, PlayContext, PlayContextProvider
from ..blackboard import BlackboardKeys, BlackboardClient, robot_status_key

if TYPE_CHECKING:
    from ...runtime import SoccerKit


class _DataLeaf(py_trees.behaviour.Behaviour):
    """Shared base for data-layer leaves; always returns SUCCESS."""

    def __init__(self, name: str):
        super().__init__(name)
        self.blackboard = BlackboardClient(name=name)


class UpdateClock(_DataLeaf):
    """Write current time to ``/clock/now`` and reset frame-level flags."""

    def __init__(self, get_now: Callable[[], float]):
        super().__init__("UpdateClock")
        self._get_now = get_now

    def update(self) -> py_trees.common.Status:
        self.blackboard.write(BlackboardKeys.NOW, self._get_now())
        self.blackboard.write(BlackboardKeys.SAFETY_ACTIVE, False)
        return py_trees.common.Status.SUCCESS


class UpdatePlayContext(_DataLeaf):
    """Snapshot the context from :class:`PlayContextProvider` directly into ``/play_context``.

    Holding the provider here avoids an extra callback chain through runtime,
    strategy, tree, and a temporary cached context.
    """

    def __init__(self, provider: PlayContextProvider):
        super().__init__("UpdatePlayContext")
        self._provider = provider

    def update(self) -> py_trees.common.Status:
        context = self._provider.get_snapshot()
        self.blackboard.write(BlackboardKeys.PLAY_CONTEXT, context)
        return py_trees.common.Status.SUCCESS


class UpdateGameState(_DataLeaf):
    """Clear stale GameControlState in place using ``game_state_max_age_sec``.

    Freshness filtering is centralized in the data layer and mutates
    ``context.game_state`` in place, so strategy code reads the filtered value without a separate key.

    ``last_seen_at == 0.0`` means no topic callback has written it yet, often in
    tests, so it is not filtered to match the old ``last_topic_at <= 0.0`` behavior.
    """

    def __init__(self, kit: "SoccerKit"):
        super().__init__("UpdateGameState")
        self._kit = kit

    def update(self) -> py_trees.common.Status:
        context = self.blackboard.read(BlackboardKeys.PLAY_CONTEXT)
        now = self.blackboard.read(BlackboardKeys.NOW)
        if not isinstance(context, PlayContext) or now is None:
            return py_trees.common.Status.SUCCESS
        gs = context.game_state
        if gs is not None and not gs.is_recent(
            now, self._kit.config.strategy.game_state_max_age_sec
        ):
            context.game_state = None
        return py_trees.common.Status.SUCCESS


class UpdateRecentBall(_DataLeaf):
    """Clear a stale ball in place using ``ball_max_age_sec``.

    Like game and robot filtering, this mutates ``context.ball`` directly and does
    not use a separate blackboard key.
    """

    def __init__(self, kit: "SoccerKit"):
        super().__init__("UpdateRecentBall")
        self._kit = kit

    def update(self) -> py_trees.common.Status:
        context = self.blackboard.read(BlackboardKeys.PLAY_CONTEXT)
        now = self.blackboard.read(BlackboardKeys.NOW)
        if not isinstance(context, PlayContext) or now is None:
            return py_trees.common.Status.SUCCESS
        if context.ball is not None and not context.ball.is_recent(
            now, self._kit.config.strategy.ball_max_age_sec
        ):
            context.ball = None
        return py_trees.common.Status.SUCCESS


class UpdateRobotPoses(_DataLeaf):
    """Clear stale teammate/opponent poses in place using ``robot_pose_max_age_sec``.

    ``context.teammates[i].pose``
    The snapshot is deep-copied by the provider, so these in-place edits do not
    pollute provider internals.

    Once stale poses become None, existing ``if robot.pose is None`` checks in
    strategy and motion code work without extra ``last_seen_at`` checks.
    """

    def __init__(self, kit: "SoccerKit"):
        super().__init__("UpdateRobotPoses")
        self._kit = kit

    def update(self) -> py_trees.common.Status:
        context = self.blackboard.read(BlackboardKeys.PLAY_CONTEXT)
        now = self.blackboard.read(BlackboardKeys.NOW)
        if not isinstance(context, PlayContext) or now is None:
            return py_trees.common.Status.SUCCESS
        max_age = self._kit.config.strategy.robot_pose_max_age_sec
        for robot in context.teammates.values():
            if robot.pose is not None and not robot.is_recent(now, max_age):
                robot.pose = None
        for opponent in context.opponents.values():
            if opponent.pose is not None and not opponent.is_recent(now, max_age):
                opponent.pose = None
        return py_trees.common.Status.SUCCESS


class UpdateRobotStatus(_DataLeaf):
    """Pull one player's hardware status onto the blackboard.

    This is read-only: it calls throttled ``poll_runtime_status`` via
    :class:`RobotServices`, writes ``/robot_status/{player_id}``, and lets SafetyOverrides own side effects.

    Without bound services, such as tests or dry-run, it writes a default
    :class:`RobotRuntimeStatus` so guards naturally take the normal branch.
    """

    def __init__(self, kit: "SoccerKit", player_id: int):
        super().__init__(f"UpdateRobotStatus({player_id})")
        self._kit = kit
        self._player_id = player_id

    def update(self) -> py_trees.common.Status:
        now = self.blackboard.read(BlackboardKeys.NOW)
        services = self._kit.robot_services()
        if services is None or now is None:
            status = RobotRuntimeStatus()
        else:
            status = services.poll_runtime_status(self._player_id, now)
        self.blackboard.write(robot_status_key(self._player_id), status)
        return py_trees.common.Status.SUCCESS
