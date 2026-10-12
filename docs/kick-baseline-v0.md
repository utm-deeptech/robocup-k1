# K1 kick baseline — 20 trials

Completed on 12 October 2026. **The baseline scored 0 goals in 20 trials.**
There were **19 failed attempts and 1 short ball launch**. The controlled test
shows that the current setup rarely produces contact after it starts the kick
skill. This is the baseline observation; the underlying cause has not yet been
assigned to localization, targeting, alignment, or execution.

## Results

| Measurement | Result |
|---|---:|
| Completed trials | 20: five positions, four repetitions each |
| Goals | 0 / 20 (0%) |
| Wide / out | 0 / 0 |
| Failed attempts (`missed_contact`) | 19 |
| Short launch: ball stopped inside field | 1 |
| Trials with a kick activation | 17 |
| Trials with no activation before the 120-second limit | 3 |
| Activations followed by no measured shot/contact | 16 |
| Measurable initial ball directions | 1 |
| Mean absolute direction error vs brain's requested direction | 3.19° (n=1) |
| Maximum absolute direction error vs brain's requested direction | 3.19° (n=1) |
| Mean / maximum error vs true goal-center direction | 7.69° / 7.69° (n=1) |

**Do not read 3.19° as evidence of accurate kicking.** Only trial 8 produced a
measurable trajectory. Its first contact was at simulation time 1915.244 s,
**1.532 s after a `start=false` kick command** at 1913.712 s. These timestamps
cannot establish a clean strike while RLVisionKick was active. There are no
confirmed active-skill strikes from which to estimate its intrinsic kick aim.
For that narrower measure, mean and maximum error are **unavailable**.

The one measured ball traveled approximately from (1.00, 1.50) toward
(2.50, 1.21) and stopped inside the field. Its fitted initial direction was
−6.36°. The fit used 66 physics samples over the initial 0.10–0.80 m of motion
and was independently reproduced from the stored raw recording. See the CSV
for exact launch coordinates; the approximate coordinates here are rounded.

| Requested ball position (m) | Trials | Goals | Failed attempts | Short launches |
|---|---:|---:|---:|---:|
| (0, 0) | 4 | 0 | 4 | 0 |
| (1, -1.5) | 4 | 0 | 4 | 0 |
| (1, 1.5) | 4 | 0 | 3 | 1 |
| (2, -2) | 4 | 0 | 4 | 0 |
| (2, 2) | 4 | 0 | 4 | 0 |

## What was held fixed

The source checkpoint is `v0-two-robot-working` (commit `d9fce87`) on
`local/sim-autonomy`. All files under `src/brain` and `src/vision` remain
identical to that tag. Frozen local configs, enhanced trees, and ONNX model
SHA-256 checks passed before the run and in the final audit. No behavior or
parameter tuning was performed, and no new model was trained.

Both robots remained in the scene. The striker ran the camera-based official
vision/brain stack and the enhanced tree. The opponent remained a stationary
defender near (4.48, 0). The target goal center was (7, 0).

Each trial reset only robot1, initialized it through camera-based localization,
ran READY → SET → PLAY, placed the ball with zero velocity, and observed the
first kick attempt. The striker chose its approach and kick activation. The
test did not steer it to the ball or command a kick. A trial allowed 120 wall
seconds for approach and an 8 simulation-second window after the first kick
activation. Failed trials were retained in the goal-percentage denominator.

The test referee was a repo-local wrapper around Booster's official service.
It ended kickoff restrictions at the first PLAY frame and disabled automatic
ball replacement and inactivity restarts during trials. Goal and boundary
rules stayed enabled. This makes the varied ball positions ordinary-play
shots; these numbers are not full-match or kickoff-pass performance. Early
recorder/fixture preflight runs were excluded from the final 20-trial set.
The startup runner was improved to acknowledge localization controls and
resume after a setup interruption; this did not change agent behavior.

Ground truth came from `/soccer/sim/localization/robot_pose` and the official
physics ball/contacts stream. The recorder alone used those measurements.
The brain's subscriptions were checked: it consumed vision and odometry,
with no ground-truth pose or world subscription. The camera relay remained
local rendering infrastructure; no dependency on it was added to the agent.

## Files you can open

- Desktop summary: `/home/anas-alanqar/Desktop/K1 Kick Baseline.md`
- Desktop raw per-trial CSV: `/home/anas-alanqar/Desktop/K1 Kick Baseline.csv`
- Repository summary: `docs/kick-baseline-v0.md`
- CSV, complete row JSON, metrics, protocol, audit and integrity metadata:
  `docs/kick-baseline-v0/`
- Full raw recordings and logs (54.8 MB compressed):
  `/home/anas-alanqar/robocup_demo/.cache/kick-baseline-v0-open-play.tar.gz`

CSV positions are meters, pose headings and direction fields are radians,
error fields are degrees. Blank direction/error cells mean no measurable
launch; they are not zero errors. Activation, first contact, and launch impulse
have separate pose snapshots and message/sample ages. The computed CalcKickDir
is recovered exactly from the brain's existing `/kick_ball` direction and
heading message in ordinary play. No extra telemetry was added to the brain.

The raw archive includes every completed trial's continuous physics/ROS-state
snapshots, RPC events, startup and brain logs, referee events, and the final
measurement audit. Its SHA-256 is stored in `docs/kick-baseline-v0/integrity.json`.

## Repeat the test

Follow `docs/sim-multi-camera-workaround.md` to restore the two-robot cameras
and bridge. Copy the authored scripts from the host to `/root/robocup_demo`
in the existing container. Start the measurement referee and use a new output
folder. Keep Booster Studio's field view open.

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; nohup bash scripts/sim_kick_test_referee.sh > sim-kick-test-referee.log 2>&1 < /dev/null &'
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; source /opt/ros/humble/setup.bash; source install/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml SIM_DDS_PROFILE=/opt/booster/BoosterRos2/fastdds_profile.xml; python3 -u scripts/sim_kick_baseline.py --output .cache/kick-baseline-next-run --repeats 4'
```

The final collected run used `.cache/kick-baseline-v0-open-play`; it resumed
with `--resume` after a localization-control setup timeout. Its protocol was
verified against the saved protocol before resuming. Never mix output folders
or change positions/behavior between comparison runs.

The six measurement tests passed:

```bash
python3 tests/test_sim_kick_metrics.py
```

They check trajectory direction, angle wrapping, missing measurements,
whole-ball boundary crossing, and correct statistics with failed trials.
Detailed timing and measurement rules are in `docs/kick-baseline-protocol.md`.

## State at handover

The normal opposing-team referee has been restored in **INITIAL**. The
measurement referee and soccer demo nodes are stopped. Both robot bodies and
the camera services remain available. No dependencies were installed, no
container was recreated, and no simulator or ROS installation files changed.

**Stopped after Step 1 as requested.** Step 2 diagnosis, Step 3 behavior fixes,
and Step 4 official-match research have not been performed. The next phase
must distinguish a kick command from actual contact before treating a launch
angle as a confirmed kick-accuracy measurement.
