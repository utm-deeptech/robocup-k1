# K1 team agent: progress and next steps (2026-10-17)

Handoff note for the next session. All work below is **uncommitted** in `~/robocup_demo`.
Booster's simulator and referee were not modified (see the memory rule).

## How to run a match

```bash
cd ~/robocup_demo && bash scripts/sim_agent_match.sh
```

Booster Studio must be open. The script starts the container if needed, stops our camera pipeline
(not needed for agent-only matches), reloads our `deeptech_pitch_K1` scene (robot1 in DeepTech navy,
robot2 blue), and starts the referee, Booster's AI on robot2 (team 2) and our agent on robot1 (team 1).
Sim speed is about 0.7x real time.

Match position trace (used for all analysis): see the recorder one-liner in this session's history, or
record `scripts/sim_kick_physics_worker.py` world frames to `.cache/match_trace.jsonl`. Saved traces in the
container: `.cache/match_trace_6-2.jsonl`, `_2-3.jsonl`, `_5-5.jsonl`.

## What changed today

| Area | Change | File |
|---|---|---|
| Shirt | Scene copy with robot1 chest colour #131531; robots spawn OFF the field (referee parks penalized robots at spawn) | `scripts/make_deeptech_scene.py`, `scripts/sim_use_deeptech_scene.py` |
| Speed of sim | Match script skips camera relay/bridge/renderer | `scripts/sim_agent_match.sh` |
| Kick aim | Every kick turned right by measured drift (power 1.2: 19 deg, 1.5+: 13 deg) | `tactics/motion.py` (`kick_drift_rad`) |
| Kick power per kick | `KickTarget(Pose2D)` carries power; kick node passes it through | `tactics/targeting/attack.py`, `play/nodes.py` |
| Shooting | Within 5 m of goal and goal mouth >= 12 deg: shoot from any angle incl. sides (power 1.5 up to 3.5 m, 3.0 beyond); no long shots further out | `attack.py` (`zone_shot_target`) |
| Dribbling | Touch ~2.8 m (power 1.2) into space we reach >= 1 s before the opponent; else away from the opponent | `attack.py` (`space_dribble_target`) |
| Kick hand-off | Walk at full speed until 1.0 m from ball, then Booster visual kick (was 2.5 m) | `soccer_framework/config.py` |
| Kick-off | Own: wait 0.5 m behind ball. Opponent's: stand in the ball path just outside the centre circle | `tactics/ready_stance.py` |
| Defence | If the opponent wins the race to the ball and we are not goal-side, go to a cover point between ball and our goal | `attack.py` (`cover_target`), `play/default_roles.py` |

## Measurements

Kick test (`scripts/sim_kick_power_test.py`, robot1, one spot, kicking +x):

| Power | Roll | Drift (left) | Reliability |
|---|---|---|---|
| 1.0 | 2.0 m | 16 deg | 1 of 4 kicked |
| 1.2 | 2.8 m | 19-20 deg | good |
| 1.5 | 4.7-5.1 m | 11-15 deg | good |
| 3 | 7.7-8.2 m | 12-14 deg | good |
| 5 | 7.0-8.2 m | 12-15 deg | good |
| 7, 10 | 9-14 m | random +-35 deg | often no kick |

From match traces: robot speeds are equal (both capped at 0.8 m/s in the agent config); visual kick needs
median 1.4 s (p75 1.8 s) from 1 m to touch.

## Match results vs Booster default AI (1v1)

- 6-2 (before the kick-off and defence changes; robot2 really playing)
- 3-3 (every goal came straight from a kick-off)
- 5-5 (latest code): 4 of our 5 goals came 8-9 s after our kick-off. Booster's kick-off goals now take
  11-16 s; one kick-off was blocked.

## Next steps (in order)

1. **Clear immediately when defending.** After `cover_target` gets robot1 goal-side, it still walks around
   the ball to kick toward the opponent goal (~3 s), and robot2 scores past it (at least 2 goals in the 5-5).
   When goal-side with the opponent close, kick in the safest direction near robot1's current heading
   (sideways/forward, never toward our goal), with no turn-around.
2. **Turn while walking.** `tactics/motion.py` `_compute_velocity` stops and turns in place when the heading
   error is > 0.5 rad (`_TURN_THRESHOLD`). Let it walk while turning up to ~1.0 rad.
3. **Walking speed test, redone properly.** `scripts/sim_walk_speed_test.py` gave bad data: 5 of 12 runs got
   `API call failed, code = 100` right after reset, and no run reached its commanded speed. Wait longer
   after reset, retry set_gait/set_mode, run longer. The K1 gait allows up to ~1.0-1.2 m/s
   (`/opt/booster/Gait/configs/K1/common_module_options.lua`); our agent caps at 0.8
   (`max_linear_speed`). If 1.0+ doesn't add falls, raise it: robot2 stays at 0.8.
4. Re-check the kick drift correction from another spot or direction (it was measured only from (-4.5, 3)
   toward +x).
5. Commit when the user approves.
