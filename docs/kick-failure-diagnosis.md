# Failed-kick diagnosis: enhanced versus original robocup_demo

Measured on 2026-10-12, branch `local/sim-autonomy`. **No proposed behavior fix has been applied.**

Our changes are associated with a kick-completion regression: original upstream makes contact during a kick action in 10/20 trials and scores in 5/20; the frozen enhanced version makes no contact during a kick action and scores in 0/20. Its one short launch happens during adjustment after visual kick has stopped. The dominant failure is an activated visual skill producing no contact, coupled with the enhanced decision gates preventing the working walking `Kick` branch from being selected.

## Failure counts

| Category | Enhanced | Original upstream |
|---|---:|---:|
| Never reached the ball | 2 | 1 |
| Reached but never aligned / stuck in adjust | 0 | 0 |
| Kick started but no contact | 16 | 9 |
| Blocked by added pause/cooldown gate | 1 | 0 |
| Timeout / other | 0 | 0 |
| **Failed trials** | **19** | **10** |
| Contact during an active kick action | 0 | 10 |
| Short launch outside a kick action | 1 | 0 |
| Trials with a confirmed goal | 0 (0%) | 5 (25%) |

These are exclusive failure categories, with action activation taking precedence over distance. “Reached” means ground-truth root-to-ball-center distance <= 1 m, matching the chase/adjust zone; it does not mean the foot is touching the ball. The 16 enhanced activated failures are **RLVisionKick**, not the named walking `Kick` node. That named node never starts in the enhanced run; it starts in 10 upstream trials, with contact in all 10. Upstream starts visual RPC in 11 trials (one also has earlier walking contact); none produces contact while that RPC is active.

Trial 3 is assigned to the added gate category because it reaches the ball, briefly enters settle, but never holds the required stable alignment long enough to start either kick action. It is also predominantly stuck in adjust. This is evidence of combined alignment/gate blocking, not proof that removing the pause alone would fix it. No trial is attributed solely to cooldown.

## Per-trial evidence

[Enhanced CSV](kick-failure-diagnosis/enhanced/classification.csv) and [upstream CSV](kick-failure-diagnosis/upstream/classification.csv) record every trial's closest true distance, closest-point alignment, named `Kick` start evidence, visual RPC starts, total time and longest uninterrupted time in each BT decision, settle time, and inferred cooldown. Full intervals are in each profile's `decision-timelines.json`.

Closest-point alignment is provided separately for the brain's robot-to-ball line versus CalcKickDir, the brain heading versus CalcKickDir, true heading versus CalcKickDir and goal center. These are different quantities. Target sample age is retained so stale values are visible. BT selection is logged; because the selected `Kick` node is a synchronous branch, selection is start evidence rather than an independent internal onStart event probe.

The following condensed tables give total simulation seconds in find/chase/adjust/visual/Kick/pause. Cooldown overlaps these decisions and must not be added to them. `d` is minimum true root-to-ball distance. `align` is the signed brain robot-to-ball-line error versus CalcKickDir at that closest sample; heading errors and target age are in the CSV. `K` means the named `Kick` ever started. Time spent in unknown/assist/cross is also retained in the CSV.

### Enhanced

| Trial | Category | d (m) | align (°) | K | Find | Chase | Adjust | Visual | Kick | Pause | Cooldown |
|---|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | started/no contact | 0.238 | 18.0 | no | 3.71 | 2.29 | 8.19 | 6.45 | 0.00 | 1.22 | 2.89 |
| 2 | started/no contact | 0.252 | -11.4 | no | 14.75 | 38.00 | 9.41 | 8.90 | 0.00 | 3.30 | 3.00 |
| 3 | gate blocked | 0.187 | -1.0 | no | 16.61 | 11.15 | 71.60 | 0.00 | 0.00 | 0.37 | 0.00 |
| 4 | started/no contact | 0.188 | -1.0 | no | 0.00 | 8.41 | 14.92 | 7.01 | 0.00 | 5.12 | 1.50 |
| 5 | started/no contact | 0.225 | -25.6 | no | 0.00 | 9.87 | 27.56 | 8.77 | 0.00 | 5.99 | 3.00 |
| 6 | started/no contact | 0.292 | -5.5 | no | 0.00 | 2.22 | 13.51 | 8.88 | 0.00 | 5.72 | 3.00 |
| 7 | never reached | 2.261 | -156.1 | no | 5.39 | 12.82 | 82.81 | 0.00 | 0.00 | 0.00 | 0.00 |
| 8 | short after stop | 0.226 | -18.9 | no | 0.00 | 7.28 | 8.48 | 8.09 | 0.00 | 1.75 | 3.00 |
| 9 | started/no contact | 0.165 | -16.5 | no | 28.91 | 48.98 | 8.09 | 7.01 | 0.00 | 3.72 | 1.50 |
| 10 | started/no contact | 0.191 | -13.4 | no | 0.00 | 6.78 | 9.69 | 7.01 | 0.00 | 1.51 | 1.50 |
| 11 | started/no contact | 0.574 | -0.9 | no | 0.00 | 2.48 | 0.54 | 7.01 | 0.00 | 3.58 | 1.50 |
| 12 | started/no contact | 0.233 | -10.0 | no | 0.00 | 4.81 | 4.37 | 9.00 | 0.00 | 3.78 | 3.00 |
| 13 | started/no contact | 0.305 | -1.3 | no | 0.00 | 5.46 | 3.62 | 8.86 | 0.00 | 2.25 | 3.00 |
| 14 | started/no contact | 0.227 | 8.2 | no | 0.00 | 6.92 | 6.17 | 8.91 | 0.00 | 2.42 | 3.00 |
| 15 | started/no contact | 0.257 | -2.0 | no | 0.57 | 7.52 | 7.04 | 6.44 | 0.00 | 5.44 | 3.00 |
| 16 | started/no contact | 0.513 | -0.6 | no | 0.00 | 2.78 | 0.67 | 8.86 | 0.00 | 1.19 | 3.00 |
| 17 | never reached | 2.443 | -40.0 | no | 33.48 | 15.16 | 55.18 | 0.00 | 0.00 | 0.00 | 0.00 |
| 18 | started/no contact | 0.271 | -6.8 | no | 0.00 | 4.57 | 5.00 | 8.32 | 0.00 | 3.69 | 4.25 |
| 19 | started/no contact | 0.176 | -8.0 | no | 0.86 | 8.15 | 34.45 | 7.02 | 0.00 | 4.10 | 1.50 |
| 20 | started/no contact | 0.230 | -63.4 | no | 8.96 | 11.53 | 52.37 | 7.03 | 0.00 | 3.78 | 1.50 |

### Original upstream

| Trial | Category | d (m) | align (°) | K | Find | Chase | Adjust | Visual | Kick | Pause | Cooldown |
|---|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | started/no contact | 2.083 | -3.0 | no | 0.00 | 0.00 | 0.00 | 10.54 | 0.00 | 0.00 | 0.00 |
| 2 | Kick contact | 0.126 | 77.2 | yes | 0.00 | 8.23 | 14.86 | 0.00 | 95.40 | 0.00 | 0.00 |
| 3 | never reached | 6.933 | 27.3 | no | 91.70 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 4 | Kick contact | 0.124 | -27.0 | yes | 8.52 | 25.84 | 84.60 | 0.00 | 2.97 | 0.00 | 0.00 |
| 5 | Kick contact | 0.140 | 10.4 | yes | 0.00 | 9.30 | 13.95 | 0.00 | 96.98 | 0.00 | 0.00 |
| 6 | Kick contact | 0.161 | -34.7 | yes | 84.54 | 14.33 | 10.98 | 0.00 | 9.65 | 0.00 | 0.00 |
| 7 | Kick contact | 0.202 | -0.6 | yes | 16.30 | 22.51 | 39.00 | 0.00 | 42.36 | 0.00 | 0.00 |
| 8 | Kick contact | 0.206 | -0.5 | yes | 0.00 | 5.74 | 5.18 | 10.54 | 2.75 | 0.00 | 0.00 |
| 9 | Kick contact | 0.165 | -34.2 | yes | 0.00 | 6.59 | 15.10 | 0.00 | 97.15 | 0.00 | 0.00 |
| 10 | Kick contact | 0.165 | 19.1 | yes | 9.70 | 17.65 | 83.27 | 0.00 | 11.39 | 0.00 | 0.00 |
| 11 | started/no contact | 1.903 | -9.3 | no | 0.00 | 0.00 | 0.00 | 10.56 | 0.00 | 0.00 | 0.00 |
| 12 | Kick contact | 0.160 | -36.2 | yes | 0.00 | 4.46 | 6.55 | 10.55 | 2.70 | 0.00 | 0.00 |
| 13 | started/no contact | 3.413 | -45.8 | no | 0.14 | 0.08 | 0.00 | 10.33 | 0.00 | 0.00 | 0.00 |
| 14 | started/no contact | 3.246 | 33.5 | no | 8.88 | 7.88 | 0.02 | 2.03 | 0.00 | 0.00 | 0.00 |
| 15 | started/no contact | 2.869 | -52.1 | no | 0.00 | 1.78 | 0.00 | 8.87 | 0.00 | 0.00 | 0.00 |
| 16 | started/no contact | 1.916 | 140.3 | no | 0.79 | 2.23 | 0.00 | 7.53 | 0.00 | 0.00 | 0.00 |
| 17 | started/no contact | 3.399 | 35.4 | no | 0.00 | 0.00 | 0.00 | 10.56 | 0.00 | 0.00 | 0.00 |
| 18 | started/no contact | 2.886 | 13.8 | no | 0.00 | 0.00 | 0.00 | 10.58 | 0.00 | 0.00 | 0.00 |
| 19 | started/no contact | 2.465 | 118.5 | no | 9.80 | 12.12 | 0.00 | 10.57 | 0.00 | 0.00 | 0.00 |
| 20 | Kick contact | 0.172 | 12.0 | yes | 0.00 | 8.98 | 6.10 | 0.00 | 104.33 | 0.00 | 0.00 |

## What the logs establish

- Enhanced trials 7 and 17 never approach within 1 m: minima 2.261 m and 2.443 m.
- Trial 3 approaches to 0.187 m, but spends 71.596 s in adjust out of 99.816 s observed PLAY. Its longest settle is 0.214 s versus the required 0.500 s; total settle is 0.374 s. At the closest sample, its brain line error is only -1.04°, but brain heading error is 30.78° and ball yaw is 33.75°; true heading versus goal is -23.26°. A good robot-to-ball line alone does not satisfy the added three-part gate. Neither kick starts.
- The 16 activated failures start at true distances 0.260–0.714 m (median 0.414 m). First RPC-active intervals last 2.686–6.510 s (median 6.500 s). Root displacement is 1.6–37.2 mm (median 8.3 mm), with zero contacts during those intervals. Thirteen hit our enforced 7,000 ms node bound; the shorter attempts exit following loss of the ball. A torso measurement alone does not prove no leg swing.
- In upstream, native logs explicitly receive `Start Visual Kick V2 Command Received`, and correlated API 2038 responses report status 0. This proves acceptance, not successful execution. Passive foot kinematics were added for trials 15–20: four complete visual intervals (trial 16 twice, 17, 18) show only 5–10 mm fore/aft foot variation and <=0.4 mm vertical variation after the first 300 ms. Trial 19 and the second trial-15 interval have small leg movements but no contact. By contrast trial 20 walking `Kick` shows 0.08–0.15 m vertical and 0.10–0.28 m fore/aft foot excursions and produces contact. These upstream visual attempts are far from the true ball, so this does not isolate the enhanced near-ball skill internals.
- Some native logs say `VisualKickBodyControl is not running, cannot start action`; their timestamps correspond to reset/setup and head-action API 2004, before the trial visual RPC. They are not evidence that the in-trial API 2038 was rejected.

## Trigger and the 1.53 s gap

In enhanced trial 8, visual RPC starts at simulation time 1911.092, stops at 1913.712, and the first contact occurs at 1915.244, **1.532 s after stop**, with BT decision `adjust`. The root moves only 5.0 mm while that first visual command is active, then moves 154.3 mm from stop to contact. This is consistent with adjustment walking making contact after the visual attempt exits; it is not evidence of a successful delayed visual strike or a fixed 1.53 s kick-motion delay. The cooldown is 1.5 s but permits adjustment motion and is not a motion freeze.

The two actions have different implementations:

| Parameter | Value in both trees | Actual effect |
|---|---|---|
| `Kick.min_msec_kick` | 1000 ms | Walking duration base; implementation adds estimated ball range / speed_limit × 1000 ms |
| `Kick.speed_limit` | 0.8 m/s | Walking speed cap; starts at 0.5 and increases by 0.1 per tick |
| `Kick.msecs_stablize` | 1000 ms | Declared BT port, but never read by the `Kick` implementation; it supplies no stabilization delay |
| `RLVisionKick.min_msec_kick` | 1500 ms | Guards far-ball/high-cost exits; it does not guarantee contact or delay an already-started strike |
| Visual startup deceleration | 500 ms | Happens before API 2038 start; present upstream too |
| `RLVisionKick.max_msec_kick` | 7000 ms | Enforced by our enhanced C++; declared but not enforced by original upstream |
| Added precision settle / cooldown | 500 / 1500 ms | Enhanced decision gate; separate from `msecs_stablize` |

The local README documents auto visual kick for K1, and the installed K1 motion configuration registers V1/V2 controls and models. Thus it is not accurate to claim K1 cannot support visual kick. **It is accepted but does not complete contacts in this current two-robot simulator setup.** Its deeper cause (native target routing/state/model behavior) is not isolated. `/robot1/kick_ball` has no publisher while the brain publishes global `/kick_ball`, but global native subscribers also exist; topic names alone do not prove a routing bug. No speculative routing or simulator change has been applied.

## A/B method and limits

Original brain revision: `45b0e16889c25a6f01ec43952bcec685c303ba62`, branch `sandbox/support_2026_game_controller`. All 40 original source files are byte-verified and built in `.cache/upstream-ab/install`; the enhanced install is retained. `game.xml`, original defaults, original locator and original C++ are used. The only local override is the earlier sim I/O/team configuration from `c72d6e8`, with no RL parameter override. Original auto visual range max is 4 m and angle 0.8 rad; enhanced local limits are 1 m and 0.2 rad. Camera relay, vision fixes, first-robot bridge, defender and test referee remain the same. See the saved protocol and source manifest for hashes.

Both profiles use the same five ball positions, four repetitions each, stationary opponent at (4.5,0), vision localization, and READY/SET/PLAY placement protocol. Simulator truth is confined to test observers. The original recorder waits 8 s after a first visual activation but, when only walking `Kick` happens, can run until 120 s; consequently the raw upstream `trials.csv` undercounts walking contacts and trajectory fits are unavailable. The corrected classification reads raw physics throughout each recorded trial. As a narrower matched measure, contact during the **first kick action within 8 s** is upstream 8/20 versus enhanced 0/20. Full-trial contact is 10/20 versus 0/20; full-trial goals are 5/20 versus 0/20. A full walking-action-aware harness is needed before treating these as identical-duration accuracy trials.

No random seeds were fixed. After upstream trials 1–2, orphan DDS shared-memory files filled the existing 256 MB `/dev/shm`, stalling fixture physics/cameras during setup of trial 3. The incomplete setup was preserved and excluded; the existing container was restarted in place and the same two-robot scene/helpers restored. The built-in `/usr/local/booster_robot/cleanup_orphan_shm.sh` now removes only unused DDS files between trials. No container recreation, dependency installation, Docker/NVIDIA configuration edits, simulator edits, or GUI action occurred. Host camera port mappings changed on restart; the renderer was reconnected to the current camera hub. Per-trial sim clocks accommodate the restart; trials 1–2 precede it. This and the unseeded single batch limit causal precision.

## Proposed one-change experiment — awaiting confirmation

Add just `RLVisionKick.enableAutoVisualKick: false` to **the local sim override** `src/brain/config/config_local.yaml`. Keep every other BT parameter, alignment requirement, pause/cooldown value and walking speed unchanged. This sends eligible aligned attempts through the existing walking `Kick` instead of the visual branch that makes no contact. Then rerun the same 20 placements with action-aware logging and compare completion, goals and alignment to the frozen baseline. This is a measured workaround for the visual path, not a claim that the native controller's internal defect has been repaired. If it exposes an alignment blockage, measure that separately before another change.

**This parameter has not been changed.** Source under `src/brain` and `src/vision` still matches `v0-two-robot-working`.

## Artifacts, verification and handover

- Baseline raw archive: `.cache/kick-baseline-v0-open-play.tar.gz`, SHA-256 `414041c1d644d7b47163065a915469d911c8491149f373f2bf1166789ad98075`.
- Upstream raw archive: `.cache/kick-upstream-v0.tar.gz`, SHA-256 `8c3002cf0a2534e39acba23771ce87eb5a50a8fa87170a464180581251d01ec9` (72 MiB compressed). Includes world/BT/RPC frames, events, brain logs, passive feet observations, available native logs, protocol and shared-memory maintenance records. Native logs begin with trial 4; passive feet observations begin in trial 15.
- [Enhanced decision plot](kick-failure-diagnosis/enhanced/decision-timelines.png) and [PDF](kick-failure-diagnosis/enhanced/decision-timelines.pdf).
- Reproduce offline classification: `python3 scripts/sim_kick_failures.py .cache/kick-upstream-v0 --profile upstream --output docs/kick-failure-diagnosis/upstream`; use the baseline extracted folder and `--profile enhanced` for our run.
- Live original profile: use the pinned original source/install overlay described above, then `python3 -u scripts/sim_kick_baseline.py --profile upstream --output .cache/NEW_OUTPUT --repeats 4` inside the existing container with helpers running. Never reuse a completed output folder for a different behavior.
- Nine meaningful checks pass: six trajectory/statistics tests and three classification tests (trial/reset boundaries, legacy contacts without visual activation, contact after visual stop). Isolated upstream build, Python compilation and launcher shell syntax passed.
- No packages or dependencies installed. Tools use the existing Python/ROS/MuJoCo/Matplotlib environment.
- The normal opposing-team referee is restored in INITIAL; soccer demo and measurement processes are stopped. Both robot bodies, relay, bridge and renderer remain available. Default launcher still uses enhanced behavior; the original overlay was only sourced by A/B processes.

Step 3 is waiting for the user's confirmation. Official-match research/building is outside this revised Step 2 and has not started.
