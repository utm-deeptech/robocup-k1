# HTWK K1 dribble (RoboCup 2025 KidSize champions, on Booster K1)

Source: https://github.com/NaoHTWK/Firmware-Salvador, cloned to `docs/research/repos/htwk-firmware/`. Files: `agents/dribble_k1.cpp`, `utils/dribbling_direction/dribbling_direction.h`, `team_strategy/robocup_strategy.cpp`.

Key fact: their K1 striker order `MoveBallGoalOrder` maps to **walk-dribble only**. There is a `// TODO: Implement pew shot.` in the code. They won by moving the ball steadily and losing it rarely, not by shooting.

## Dribble direction: a smooth vector field over the field
Field coordinates: x toward the opponent goal, half-length L = 7, half-width W = 4.5, quarter q = L/4 or W/4. The direction is the sum of anchor vectors, each weighted by `1 / (0.1 + |pos - anchor|^2)`, then normalised:

| anchor (x, y) | vector |
|---|---|
| (−L, −W) (−L, −W/4) (−L, 0) (−L, W/4) (−L, W) | (2, 2) (2, −2) (2, 0) (2, 2) (2, −2) |
| (0, −W) (0, 0) (0, W) | (1, 0.5) (1, 0) (1, −0.5) |
| (L/4, −W) (L/4, 0) (L/4, W) | (1, 2) (5, 0) (1, −2) |
| (L, −W) (L, −W/4) (L, 0) (L, W/4) (L, W) | (−1.5, 3.5) (−0.7, 1.0) (5, 0) (−0.7, −1.0) (−1.5, −3.5) |

Effect: in your own half the ball goes forward, near the sidelines it curves inward, and near the opponent corners it is pulled back toward the goal mouth instead of over the end line.

## Walk-dribble controller (relative ball pos b, dribble dir d, both in the robot frame)
```
ball_dist = |b|;  ball_angle = atan2(b.y, b.x - 0)    # b.y offset -0.05 (foot)
bturn_factor   = clamp(angle(d) * 0.35, -1, 1)          # how much we must orbit the ball
forward        = clamp(1 - |bturn_factor|*damp - |b.y|*damp_y, 0, 1)   # ×0.3 if corridor blocked
dist_corr      = clamp(ball_dist - 0.25, -1, 1) * (1 - clamp(|ball_angle|/(pi/2),0,1))
angle_corr     = ball_angle * 2*clamp((ball_dist-0.3)/0.3, 0.5, 1) * clamp(|angle(d)|*0.7, 0.6, 1)
side_corr      = (ball_angle - clamp(ball_angle,-0.3,0.3))*0.6 + b.y*1.0*(1-...)
vx  = dist_corr + forward
vy  = -0.7 * bturn_factor + side_corr
vyaw=  0.7 * bturn_factor + angle_corr
```
`damp = 2.8 − spread` and `damp_y = 2.5 − spread`. `spread` is ~1 near our goal or the opponent goal mouth and 0 in midfield. Close to the goal it tolerates more sideways error and keeps pushing.

## Team logic worth copying (robocup_strategy.cpp)
- Striker request with the timestamp-latest winner. Switch only when `other_time > max(1.1·mine, mine + 0.75 s)`.
- `isRogueStriker`: act as striker if `max(1.2·mine, mine + 1.5) < striker_time + detour`.
- Supporter target low-pass: `filter = 0.9·filter + 0.1·target`, reset if the jump is > 0.2·field length.
- Supporters treat the ball (r = 1 m) and the striker (r = 0.75 m) as repulsive obstacles.
- Goalie: on the own-goal→ball line, `clamp(dist − 0.5, 0, 0.5)` in front of the goal.
- Penalty return: walk forward 0.6 m/s for 3 s if localization quality is < 0.7, then wait for localization.
