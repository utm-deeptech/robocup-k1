"""Chase/kick decisions and pass scoring.

Callers first use :mod:`predicates` to rule out sideline/recovery cases, then use
this module to choose this tick's kick target:

center view: pass, then shoot, then dribble
side view: pass if possible, otherwise clear, without shooting
choose best passing teammate by score
generic lane-obstacle score
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from ...soccer_framework import (
    BallState,
    GameControlState,
    Pose2D,
    SetPlay,
    SoccerConfig,
    PlayContext,
)
from ..geometry import clamp
from ..navigation import Obstacle, ObstacleCollector
from ..geometry import TeamFieldFrame
from . import recovery
from .predicates import ball_near_sideline


__all__ = [
    "PlayerAllowed",
    "best_pass_target",
    "cover_target",
    "dribble_target",
    "KickTarget",
    "space_dribble_target",
    "zone_shot_target",
    "kick_reason",
    "lane_clear_score",
    "select_clear_or_pass_target",
    "select_kick_target",
    "shot_lane_is_clear",
    "should_make_restart_touch",
]


# Shared with upper layers: test whether a teammate can legally join tactics, excluding penalized/substitute players.
PlayerAllowed = Callable[[GameControlState, int], bool]


# Top-level selection


def select_kick_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    player_id: int,
    context: PlayContext,
    is_player_allowed: PlayerAllowed,
) -> Pose2D:
    """Decide this tick's aim target for a center chaser.

    Decision order: sideline recovery, restart touch, best pass, clear shot lane,
    and finally dribble forward.
    """

    ball = context.known_ball
    if ball_near_sideline(config, ball):
        return (zone_shot_target(config, field, obstacles, context)
                or recovery.sideline_recovery_target(config, field, ball))

    game = context.game
    if game is not None and should_make_restart_touch(config, game):
        teammate = best_pass_target(
            config, obstacles,
            player_id, context, is_player_allowed,
        )
        if teammate is not None:
            return Pose2D(teammate.x, teammate.y, 0.0)
        return dribble_target(config, field, ball)

    teammate = best_pass_target(
        config, obstacles,
        player_id, context, is_player_allowed,
    )
    if teammate is not None:
        return Pose2D(teammate.x, teammate.y, 0.0)

    # k1team: shoot only inside the shooting zone; further out, carry the ball into space.
    shot = zone_shot_target(config, field, obstacles, context)
    if shot is not None:
        return shot
    return space_dribble_target(config, field, obstacles, player_id, context)


@dataclass(frozen=True)
class KickTarget(Pose2D):
    """k1team: a kick aim point that also carries the kick power to use."""

    power: float = 0.0


# k1team kick powers, from scripts/sim_kick_power_test.py (ball roll on the sim pitch):
# 1.2 -> ~2.8 m, 1.5 -> ~5 m, 3 -> ~8 m. Power 1.0 often fails to kick at all.
_TOUCH_POWER = 1.2
_TOUCH_ROLL_M = 2.8
_NEAR_SHOT_POWER = 1.5
_FAR_SHOT_POWER = 3.0

# k1team shooting zone: within this distance of the goal centre, shoot from any angle
# (including from the side) when the goal mouth is wide enough from the ball.
_SHOT_ZONE_M = 5.0
_NEAR_SHOT_M = 3.5
_MIN_GOAL_MOUTH_DEG = 12.0
_ZONE_LANE_MIN = 0.3  # lane score needed in the zone (open field needs 0.55)

# k1team: score several aim points instead of only the goal centre (Rhoban/Berlin United
# style). Goal width 2.6 m; keep ~0.5 m inside each post for the kick's aim spread.
_SHOT_AIM_YS = (0.0, 0.4, -0.4, 0.8, -0.8)

# k1team space dribble: candidate directions (rad, relative to the line to goal centre).
_SPACE_ANGLES = (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2)
# Measured in the 6-2 match trace (2026-10-17): from 1 m away, Booster's visual kick needs a
# median 1.4 s (p75 1.8 s) to touch the ball. We walk at full speed until 1 m (kick hand-off).
_KICK_SETUP_S = 1.8
_HANDOFF_M = 1.0
_MIN_LEAD_S = 1.0  # only play into space we win by at least this much
_PROGRESS_WEIGHT = 2.0  # a full touch straight at goal is worth a 2 s lead
_MAX_LEAD_S = 1.0  # a lead beyond 1 s is safe enough; it earns nothing more
_FIELD_MARGIN_M = 0.6  # keep the touch this far inside the lines
_GOAL_LINE_KEEPER_M = 1.0  # opponent this close to its goal line counts as a keeper


# k1team cover defence: when the opponent will reach the ball first and we are not between
# the ball and our goal, get goal-side (on the ball-to-goal line) instead of chasing from behind.
_COVER_DIST_M = 1.5  # cover point distance from the ball, toward our goal
_COVER_RACE_MARGIN_M = 0.5  # opponent must be this much closer to the ball than us
_GOAL_SIDE_MARGIN_M = 0.3
_PASS_BALL_CLEARANCE_M = 0.7  # walk around the ball, never through it toward our goal


def cover_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    player_id: int,
    context: PlayContext,
) -> Pose2D | None:
    """Goal-side cover point while the opponent wins the ball; None means chase normally."""

    ball = context.known_ball
    me = context.teammates.get(player_id)
    opponents = [r.pose for r in context.opponents.values() if r.pose is not None]
    if me is None or me.pose is None or not opponents:
        return None
    goal_x = field.own_goal_x()
    my_dist = math.hypot(me.pose.x - ball.x, me.pose.y - ball.y)
    their_dist = min(math.hypot(p.x - ball.x, p.y - ball.y) for p in opponents)
    ball_to_goal = math.hypot(goal_x - ball.x, ball.y)
    me_to_goal = math.hypot(goal_x - me.pose.x, me.pose.y)
    if me_to_goal < ball_to_goal - _GOAL_SIDE_MARGIN_M:
        return None  # already goal-side: challenge for the ball
    if their_dist + _COVER_RACE_MARGIN_M >= my_dist:
        return None  # we can win the race
    ux, uy = (goal_x - ball.x) / ball_to_goal, -ball.y / ball_to_goal
    d = min(_COVER_DIST_M, max(0.0, ball_to_goal - 0.5))
    tx, ty = ball.x + ux * d, ball.y + uy * d
    # If the ball lies on our straight path, detour beside it on our side.
    sx, sy = tx - me.pose.x, ty - me.pose.y
    seg = math.hypot(sx, sy)
    if seg > 1e-6:
        along = ((ball.x - me.pose.x) * sx + (ball.y - me.pose.y) * sy) / seg
        cross = ((ball.x - me.pose.x) * sy - (ball.y - me.pose.y) * sx) / seg
        if 0.0 < along < seg and abs(cross) < _PASS_BALL_CLEARANCE_M:
            side = 1.0 if cross >= 0.0 else -1.0  # perpendicular toward our side of the ball
            px, py = -uy * side, ux * side
            tx = ball.x + px * (_PASS_BALL_CLEARANCE_M + 0.2) + ux * 0.3
            ty = ball.y + py * (_PASS_BALL_CLEARANCE_M + 0.2) + uy * 0.3
    tx, ty = field.clamp_inside_field(Pose2D(tx, ty, 0.0)).x, field.clamp_inside_field(Pose2D(tx, ty, 0.0)).y
    return Pose2D(tx, ty, field.face_ball_theta(tx, ty, ball))


def zone_shot_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    context: PlayContext,
) -> KickTarget | None:
    """Shot from inside the shooting zone, from any angle; None outside it or when blocked.

    Picks the clearest aim point, preferring the far post when shooting from a side.
    """

    ball = context.known_ball
    goal_x = field.opponent_goal_x()
    distance = math.hypot(goal_x - ball.x, ball.y)
    if distance > _SHOT_ZONE_M:
        return None
    half_goal = config.goal_width / 2.0
    mouth = abs(math.atan2(half_goal - ball.y, goal_x - ball.x)
                - math.atan2(-half_goal - ball.y, goal_x - ball.x))
    if math.degrees(mouth) < _MIN_GOAL_MOUTH_DEG:
        return None
    opponents = obstacles.opponent_obstacles(context)
    best, best_score = None, -1.0
    for aim_y in _SHOT_AIM_YS:
        score = lane_clear_score(config, ball.x, ball.y, goal_x, aim_y, opponents)
        if abs(ball.y) > 1.0 and aim_y * ball.y < 0:
            score += 0.1  # far post from a side: harder for a keeper to cover
        if score > best_score + 0.05:
            best, best_score = aim_y, score
    if best is None or best_score < _ZONE_LANE_MIN:
        return None
    power = _NEAR_SHOT_POWER if distance <= _NEAR_SHOT_M else _FAR_SHOT_POWER
    return KickTarget(goal_x, best, 0.0, power=power)


def best_shot_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    context: PlayContext,
) -> Pose2D | None:
    """Clearest aim point across the goal mouth; None when every lane is blocked."""

    ball = context.known_ball
    opponents = obstacles.opponent_obstacles(context)
    goal_x = field.opponent_goal_x()
    best, best_score = None, -1.0
    for aim_y in _SHOT_AIM_YS:  # ordered centre-first, so ties keep the safer aim
        score = lane_clear_score(config, ball.x, ball.y, goal_x, aim_y, opponents)
        if score > best_score + 0.05:
            best, best_score = aim_y, score
    if best is None or best_score < 0.55:
        return None
    return Pose2D(goal_x, best, 0.0)


def space_dribble_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    player_id: int,
    context: PlayContext,
) -> KickTarget:
    """Touch the ball ~2.8 m into space we reach before any opponent, then chase it.

    Each candidate spot is scored by our time lead over the nearest opponent (both at max
    walking speed; we also pay the measured kick set-up time). Among spots we win by at least
    ``_MIN_LEAD_S`` the most goalward wins; if none, the spot with the largest lead.
    """

    ball = context.known_ball
    goal_x = field.opponent_goal_x()
    to_goal = math.atan2(-ball.y, goal_x - ball.x)
    speed = max(0.1, config.strategy.max_linear_speed)
    me = context.teammates.get(player_id)
    my_dist_to_ball = (math.hypot(me.pose.x - ball.x, me.pose.y - ball.y)
                       if me is not None and me.pose is not None else 0.0)
    opponents = [r.pose for r in context.opponents.values() if r.pose is not None]
    # A keeper on its goal line guards the goal; it only races us for touches landing
    # in front of the goal (inside the goal area).
    on_line = [p for p in opponents
               if p.x > goal_x - _GOAL_LINE_KEEPER_M and abs(p.y) < config.goal_width / 2.0 + 0.5]
    half_x = config.field_length / 2.0 - _FIELD_MARGIN_M
    half_y = config.field_width / 2.0 - _FIELD_MARGIN_M
    best, best_score = None, -math.inf
    for angle in _SPACE_ANGLES:
        heading = to_goal + angle
        x = clamp(ball.x + _TOUCH_ROLL_M * math.cos(heading), -half_x, half_x)
        y = clamp(ball.y + _TOUCH_ROLL_M * math.sin(heading), -half_y, half_y)
        ours = (max(0.0, my_dist_to_ball - _HANDOFF_M) / speed + _KICK_SETUP_S
                + math.hypot(x - ball.x, y - ball.y) / speed)
        racing = (opponents if x > goal_x - _GOAL_LINE_KEEPER_M
                  else [p for p in opponents if p not in on_line])
        theirs = min((math.hypot(p.x - x, p.y - y) / speed for p in racing), default=10.0)
        lead = theirs - ours
        progress = (math.hypot(goal_x - ball.x, ball.y) - math.hypot(goal_x - x, y)) / _TOUCH_ROLL_M
        if lead >= _MIN_LEAD_S:  # a race we win: trade extra lead for progress toward goal
            score = 100.0 + min(lead, _MAX_LEAD_S) + _PROGRESS_WEIGHT * progress
        else:  # no safe space: take the one furthest from losing, i.e. away from the opponent
            score = lead
        if score > best_score:
            best, best_score = (x, y), score
    return KickTarget(best[0], best[1], 0.0, power=_TOUCH_POWER)


def select_clear_or_pass_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    player_id: int,
    context: PlayContext,
    is_player_allowed: PlayerAllowed,
) -> Pose2D:
    """Side-lane view: pass if possible, otherwise clear toward the opponent goal without shooting or dribbling.

    Side chasers prefer clearing toward the middle rather than dribbling along the sideline into pressure.
    """

    ball = context.known_ball
    shot = zone_shot_target(config, field, obstacles, context)  # k1team: side player may shoot too
    if shot is not None:
        return shot
    if ball_near_sideline(config, ball):
        return recovery.sideline_recovery_target(config, field, ball)

    teammate = best_pass_target(
        config, obstacles,
        player_id, context, is_player_allowed,
    )
    if teammate is not None:
        return Pose2D(teammate.x, teammate.y, 0.0)
    return Pose2D(field.opponent_goal_x(), 0.0, 0.0)


# Restart touch


def should_make_restart_touch(
    config: SoccerConfig,
    game: GameControlState,
) -> bool:
    """Whether our team should actively touch the ball on restart: kickoff, throw-in, or indirect free kick."""

    return game.is_kickoff_for_team(config.team_id) or (
        game.is_restart_for_team(config.team_id)
        and game.set_play in {SetPlay.THROW_IN, SetPlay.INDIRECT_FREE_KICK}
    )


# Pass scoring


def best_pass_target(
    config: SoccerConfig,
    obstacles: ObstacleCollector,
    player_id: int,
    context: PlayContext,
    is_player_allowed: PlayerAllowed,
) -> Pose2D | None:
    """Select this tick's best legal passing target; return ``None`` when no candidate qualifies.

    Score weights are lane clearance 0.55, forward gain 0.30, center pull 0.15,
    minus distance penalty. Candidates below ``pass_min_score`` are discarded.
    """

    if not config.strategy.pass_enabled:
        return None
    ball = context.known_ball
    game = context.game
    if game is None:
        return None
    candidates: list[tuple[float, Pose2D]] = []
    for teammate_id, robot in context.teammates.items():
        if teammate_id == player_id or robot.pose is None:
            continue
        if not is_player_allowed(game, teammate_id):
            continue
        forward_gain = robot.pose.x - ball.x
        if forward_gain < config.strategy.pass_min_forward_m:
            continue
        lane_score = lane_clear_score(
            config,
            ball.x,
            ball.y,
            robot.pose.x,
            robot.pose.y,
            obstacles.opponent_obstacles(context),
        )
        distance = math.hypot(robot.pose.x - ball.x, robot.pose.y - ball.y)
        field_score = clamp(
            forward_gain / max(1.0, config.field_length),
            0.0,
            1.0,
        )
        center_score = 1.0 - clamp(
            abs(robot.pose.y) / (config.field_width / 2.0),
            0.0,
            1.0,
        )
        score = 0.55 * lane_score + 0.30 * field_score + 0.15 * center_score
        score -= clamp(distance / 12.0, 0.0, 0.25)
        if score >= config.strategy.pass_min_score:
            candidates.append((score, robot.pose))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def shot_lane_is_clear(
    config: SoccerConfig,
    field: TeamFieldFrame,
    obstacles: ObstacleCollector,
    context: PlayContext,
) -> bool:
    """Treat a shot lane as directly shootable when clearance score is at least 0.55."""

    ball = context.known_ball
    return lane_clear_score(
        config,
        ball.x,
        ball.y,
        field.opponent_goal_x(),
        0.0,
        obstacles.opponent_obstacles(context),
    ) >= 0.55


def lane_clear_score(
    config: SoccerConfig,
    start_x: float,
    start_y: float,
    target_x: float,
    target_y: float,
    obstacles: tuple[Obstacle, ...],
) -> float:
    """Generic lane-obstacle score in [0, 1], where 1 is clear and 0 is blocked.

    Project each obstacle onto the lane; if it lies within the segment and inside
    lateral clearance, reduce score proportionally. Multiple obstacles take the worst score.
    """

    if not obstacles:
        return 1.0
    seg_dx = target_x - start_x
    seg_dy = target_y - start_y
    seg_len = math.hypot(seg_dx, seg_dy)
    if seg_len < 1e-6:
        return 0.0
    dir_x = seg_dx / seg_len
    dir_y = seg_dy / seg_len
    left_x = -dir_y
    left_y = dir_x
    score = 1.0
    for obstacle in obstacles:
        rel_x = obstacle.x - start_x
        rel_y = obstacle.y - start_y
        along = rel_x * dir_x + rel_y * dir_y
        if along <= 0.0 or along >= seg_len:
            continue
        lateral = abs(rel_x * left_x + rel_y * left_y)
        clearance = max(config.strategy.pass_lane_clearance, obstacle.radius)
        if lateral < clearance:
            score = min(score, clamp(lateral / clearance, 0.0, 1.0))
    return score


# Dribble and reason text


def dribble_target(
    config: SoccerConfig,
    field: TeamFieldFrame,
    ball: BallState,
) -> Pose2D:
    """Simple dribble target: advance by ``dribble_advance_m`` along ``+x`` and pull ``y`` toward center."""

    target_x = ball.x + config.strategy.dribble_advance_m
    target_y = ball.y * config.strategy.dribble_center_pull
    return field.clamp_inside_field(
        Pose2D(target_x, target_y, field.attack_theta())
    )


def kick_reason(
    config: SoccerConfig,
    target: Pose2D,
    default: str = "chaser kick",
) -> str:
    """Choose the reason suffix from whether target points at the opponent goal center.

    When target is near the goal mouth, keep ``default``; otherwise append
    ``" to target"`` so logs distinguish shooting from pass/clear targets.
    """

    if abs(target.x) >= config.field_length / 2.0 - 0.2 and abs(target.y) < 0.2:
        return default
    return f"{default} to target"
