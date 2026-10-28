# K1 3v3 soccer strategy

## Hard rules (never break)

1. **Never modify Booster's referee or simulator** (`/usr/local/booster_robot/booster_robocup_sim/...` in container `rxlma-k1`). Fix rule violations only in our code (`src/brain`, our `scripts/`). Diagnose with the referee's event log `logs/game-control/events.jsonl`.
2. **Simulator truth is for tests only.** Our agent decides from its own perception (camera + localization). Truth may place the ball, reset robots and *measure* results in test harnesses.
3. A submitted agent never places balls, resets robots or calls match-control endpoints.
4. `src/brain/src/brain.cpp` has mixed CRLF/LF line endings: edit it byte-preserving.

## The verified kick (read before touching kick code)

The K1 "kick" in this sim is a **learned visual-kick policy that takes over the legs**: it walks up to the ball itself, from as far as ~2.5 m, lines up and shoots toward a goal point. It is not a fixed stationary kick motion. Details and measurements: [references/kick-api.md](references/kick-api.md).

Required sequence (this is what Booster's own AI does; skipping step 1 = ball never moves):
1. `ChangeMode(RobotMode::kSoccer)` (api 2000, mode 4). Walk mode is not enough.
2. `VisualKick(start=true, version=kV2)` (api 2038, JSON `version: 1` means kV2).
3. Stream `Kick` refs ~20 Hz: ball (x, y) in **robot frame**, goal (goal_x, goal_y) in robot frame, `power` in [1, 10], `robot_theta_to_field`, `dir = 0`.
4. Stop with `VisualKick(false)` only after a minimum of ~1 s active, to avoid start/stop flapping.

Measured 2026-10-15: power 1.5, ball 1 m ahead → ball travelled **8.7 m**, peak 2.7 m/s, robot stayed upright. Power 3.0 → peak 3.2 m/s.

## Strategy: what wins, from the evidence

Ranked by expected value for us. Do them in this order and measure each step.

### 1. Hand the ball to the kick policy early (biggest win)
Booster's AI (which beat us 0-11) does almost nothing clever. It enters kick mode when the ball is **< 2.5 m** away, leaves at > 3.0 m (hysteresis plus a 1.5 s exit delay) and lets the policy do approach and shot at **power 1.5**. Our old behaviour walked to the ball with our own controller, then tried a short-range kick. Copy the hysteresis, then beat it on target selection (2 and 3).

### 2. Choose the kick target, not just "goal centre"
Their AI aims at the **goal centre** whenever the lane clearance score is ≥ 0.55. Otherwise it dribble-targets 1.15 m forward with y pulled 35% toward the centre. Do better (Rhoban 2023, Berlin United):
- Score candidate targets: goal left-post-inside, centre, right-post-inside (goal width 2.6 m; aim ±0.8 m), plus "advance" points. Pick the target with the best **lane clearance** (distance from each opponent to the ball→target segment), with a bonus for targets far from the goalkeeper.
- Penalise targets that would send the ball out of bounds, or nearer to an opponent than to us (Rhoban's reward shaping).
- Use higher power only when the lane is clear and the ball is in the opponent half. Use power ~1.5 for advancing, because long, weak shots get intercepted.
- See [references/research-digest.md](references/research-digest.md) for the Rhoban MDP and value-function idea.

### 3. Exploit the opponent's known weaknesses
From reading their source ([references/opponent-booster-default-ai.md](references/opponent-booster-default-ai.md)):
- **If they lose sight of the ball, all of their robots stop** (no roles when the ball is lost). Long, fast shots or passes that break their line of sight buy free time.
- Their keeper only challenges inside its own defensive area and otherwise stands on the goal line facing the ball. Shots to the post corners beat a centred keeper.
- Their chaser is chosen by plain distance (centre slot −0.20 m, side −0.10 m). There is no prediction, so the robot nearest the ball always goes, even when it faces the wrong way.
- They do use simulator truth, so they never mis-see. Don't plan on fooling their perception.

### 4. Team roles for 3 robots (KURA, HTWK, NimbRo)
- **Striker** = robot with the lowest *time-to-ball* (distance plus turn cost), not plain distance. Switch only when the challenger is better by `max(10%, 0.75 s)` (HTWK hysteresis). Oscillation loses more than a slightly worse choice.
- **Goalkeeper**: on the own-goal→ball line, 0–0.5 m in front of the goal. Challenge only when the ball is inside the penalty area.
- **Supporter**: "shadow" offset ~1.5–2 m behind and to the side of the ball, on the side away from the nearest sideline. Low-pass filter its target (0.9 old + 0.1 new) so it doesn't jitter. Keep ≥ 0.75 m from the striker and ≥ 1 m from the ball.
- **Rogue-striker rule**: if the striker's ball estimate is stale and we see the ball closer, act as striker anyway.

### 5. Dribble as fallback (how HTWK won KidSize 2025 on the K1)
HTWK's K1 striker has **no shot**. It walk-dribbles through the ball toward a direction from a smooth vector field over the field. The field points to the goal centre, curving inward near the corners. When kick mode is unavailable, for example because the lane is blocked at close range, use walk-dribble. Controller and vector field: [references/htwk-dribble.md](references/htwk-dribble.md).

### 6. Set plays and rules
- Opponent restart: stay **≥ 1.6 m** from the ball (rule 1.45 m plus margin) until it moves ≥ 0.75 m or 10 s pass.
- Own kickoff: don't score directly if the rules forbid it. Touch first, then play.
- Returning from a penalty: walk in, and wait for localization quality before acting (HTWK).

## Testing protocol

- Probe the kick through the SDK path: `scripts/kick_probe_sdk.py` (in the container: `python3 /tmp/kick_probe_sdk.py --dist 1.0 --power 1.5`). Use `virtual_robot_name=''` on a fresh single-robot container, and `'robot1'` after the defender is attached (topics become `/robot1/...`).
- Place the ball **inside the field**. The field is 14 × 9 m, centred at 0, so |x| ≤ 7 and |y| ≤ 4.5. A trial with the ball outside the field is invalid.
- Compare behaviours on equal trial counts (≥ 20), keeping failures. The previous baseline was upstream striker 12/20 vs enhanced 9/20 with the visual kick off.
- The real benchmark is a full match vs `com.booster.default3v3ai`. Last result: **0-11** (2026-10-14, before the kick fix).

## Sources
[references/research-digest.md](references/research-digest.md) lists every paper and repository with its key takeaways. Raw PDFs and text: `docs/research/papers/`. HTWK source: `docs/research/repos/htwk-firmware/`.
