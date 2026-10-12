# Visual-kick-off comparison: result (2026-10-12, 23:45)

Both profiles: 20 trials, same 5 ball positions x 4 repeats, fixed 120 s sim window,
`RLVisionKick.enableAutoVisualKick: false`.

| Profile | Goals | Walking-Kick contact | Failed trials |
|---|---:|---:|---:|
| Enhanced (our settle/cooldown gates) | 9/20 | 13/20 | 7 (4 gate-blocked, 3 stuck in adjust) |
| Original upstream | **12/20** | **20/20** | 0 |

Decision rule (approved 12:32): upstream wins, so revert our gates and keep only the
visual-kick-off change. **Applied 2026-10-12 23:50**: see below.

Raw data: inside container `rxlma-k1:/root/robocup_demo/.cache/kick-upstream-visual-off-v1`
(909 MB). Host copy: `.cache/kick-upstream-visual-off-v1.tar.gz`.

## Applied (2026-10-12, after reboot)

Our settle/cooldown gates are opt-in C++ ports (`require_kick_alignment`, default false);
only `game_sim.xml` enabled them. `scripts/sim_soccer_autonomy.sh` now launches the upstream
`game.xml` by default (`SIM_TREE=game_sim.xml` restores the experiment). Visual kick stays
off via `config_local.yaml`. No C++ change, so the existing build was reused.

Live check after the laptop restart, single robot, built-in referee:

- Start: `bash scripts/sim_soccer_autonomy.sh --reset-robot` -> Locate Success, PLAY.
- Robot1 walked from the entrance, chased and kicked; ball reached (7.3, 1.1). **Goal, score 1.**
  Robot stayed upright (upDot 1.0) throughout.
- After a goal the sim referee teleports robot1 back to the entrance; the motion controller
  then ignores walk commands and the brain keeps its stale pose, so the robot stands still.
  Recovery: `python3 scripts/sim_initialize_match.py --reset-robot --resume` (soccer mode,
  relocalize LT+A, hand over LT+B, match keeps running). Without `--reset-robot` the entrance
  localization can lock onto the wrong x (seen: -1.5 vs true -5.0).
- After recovery: walked ~8 m, kicked, ball to (7.18, 0.71). **Goal, score 2:0**, ~40 sim s.

Not done: real 1v1 (two autonomous brains) and 3v3. 3v3 needs Booster's official match
runner deployed from Studio's GUI (see `docs/official-match-research.md`) and a decision on
whether that may replace the current local setup.
