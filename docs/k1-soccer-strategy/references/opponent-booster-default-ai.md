# Opponent: Booster default 3v3 AI (`com.booster.default3v3ai`)

Source (read-only): `/usr/share/booster-studio/resources/app/booster-native/statics/ai-agent/football3v3/com.booster.default3v3ai.agent`. It is a zip containing pure Python, under `agent/com_booster_default3v3ai/lib/python3.10/site-packages/com_booster_default3v3ai/`. Key files: `play/playbook.py`, `play/default_roles.py`, `tactics/targeting/{attack,predicates}.py`, `soccer_framework/config.py`.

## Architecture
py_trees behaviour tree, one team process for 3 robots, 3 roles per tick. **Perception is simulator truth** (`ros_truth.py`), so it never mis-sees.

Field: adult size **14 × 9 m**, goal width 2.6 m, penalty area 3 × 6 m, goal area 1 × 4 m, circle radius 1.5 m, penalty spot 2.1 m.

## Roles
- Fixed slots: player 1 = CENTER, player 2 = SIDE, player 3 = KEEPER.
- **Chaser** = lowest `ball_claim_score`: distance − 0.20 (CENTER) or − 0.10 (SIDE). The keeper scores distance − 0.75 only when the ball is in its defensive area, otherwise distance + 14. Ties within a margin go to the lowest ID.
- **Supporter**: `support_target`, depth 1.05 m behind the ball carrier.
- **Goalkeeper**: guards the goal line. When the ball is in its defensive area it kicks toward the opponent goal centre, or toward a sideline-recovery point if the ball is near a sideline.
- **When the ball is lost, no roles are assigned and every robot stops** (`waiting_command`, "stop when blind").

## Attack decision (`select_kick_target`)
In order: sideline recovery → restart touch → best pass (score: 0.55 lane + 0.30 forward gain + 0.15 centre pull; lane clearance 0.75 m) → **goal centre if lane clear score ≥ 0.55** → dribble target (ball.x + 1.15, ball.y × 0.65). The SIDE robot passes or clears and never shoots.

## Motion
Max speed 0.8 m/s linear and 1.0 rad/s angular. Kick via SoccerKickManager: enter < 2.5 m, exit > 3.0 m, power 1.5 (see kick-api.md).

## Exploitable weaknesses
1. Always aims at the **goal centre**, so a goalkeeper standing centred blocks many shots.
2. Their keeper also guards the centre, so shots aimed inside the posts (±0.8 m) are better.
3. Stops when blind. They use truth, so in practice "blind" means the ball is out of play or not published. That makes this one weak, so don't rely on it.
4. Chaser selection ignores heading and opponents, and nobody marks. A second attacker arriving from the side gets free shots.
5. Low kick power (1.5) means shots are slow (~2.7 m/s), so a goalkeeper that tracks the ball line can intercept.
6. The SIDE robot never shoots. Its shots are only clears, so the CENTER robot is the only real scoring threat to mark.
