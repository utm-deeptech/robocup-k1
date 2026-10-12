# Kick accuracy baseline protocol

The behavior baseline is tag `v0-two-robot-working`. No BT, vision, localization,
motion, or aiming parameters are changed for this test. The test runner refuses
to run if the frozen configuration, enhanced tree, or model checksums differ.
Test helpers observe and place objects; they do not supply ground truth to the
brain. No simulator source is modified.

## Trial definition

Run four interleaved repetitions of five positions, in this order:
`(0, 0)`, `(1, -1.5)`, `(1, 1.5)`, `(2, -2)`, `(2, 2)` meters.
The opponent's goal center is `(7, 0)` in the simulator's world coordinate
system. The stationary opposing K1 remains near `(4.48, 0)`.

Each trial ends the previous match, stops the previous demo, resets only robot1
to the same entrance pose, selects soccer mode, starts the unchanged enhanced
demo, and requests its usual camera-based localization. It then hands over to
the test referee and waits for READY → SET → PLAY. The test referee uses the
official implementation, then calls `finish_set_play()` at the first PLAY
frame to end kickoff restrictions. Automatic ball placement, inactivity
restarts, stuck-ball clearance, and stopped-motion penalties are disabled
in this fixture. Goal and boundary detection remain enabled. These changes
are confined to a repo-local referee wrapper; the installed simulator and
agent behavior are unchanged. This measures ordinary-play shooting, not
kickoff passes or full match performance. The ball is placed at
the trial position **after PLAY**, with zero velocity, because the referee
places it at center during match initialization. Placement is verified from
physics; the striker receives the ball's position through its camera only.

Record the first RLVisionKick activation (RPC API 2038, start=true), subsequent
robot1 contacts, and the first shot-speed movement (>1 m/s after contact).
No manual approach or kick commands are sent. To isolate that shot, the harness
stops the striker once the ball has traveled over 1 m and is over 1.2 m away
from it. This stops later chase/kick attempts; it cannot improve the first
shot's aim. All later RPC activations are counted so contamination is visible.

A trial allows 120 wall seconds to approach and initiate its shot. The first
activation has an 8 simulation-second observation window for a shot, reflecting
the unchanged tree's 7-second skill duration. A launched shot is observed for
up to 30 simulation seconds. These are test limits, not BT changes. Failed
attempts are retained, with blank direction/error fields when no direction
can be measured. A setup failure aborts the suite instead of becoming a
kick result. Calibration/preflight runs are kept separately from the baseline.

## Recorded measurements

- Ball placement requested and verified, trial/repetition, simulation times.
- Robot pose from `/soccer/sim/localization/robot_pose` (via robot1 bridge) and
  brain pose from `/booster_soccer/robot_pose`, with sample ages.
- `/kick_ball` target, relative direction, power, timestamp, and the exact brain
  heading carried in that message. Activation, first contact, and first shot
  impulse have separate snapshots; do not conflate their poses.
- Live ball/robot positions and collision contacts from the official physics
  `game_control_world` stream, sampled continuously and retained as JSONL.
- Trial referee events, startup log, and brain log.

In normal play and kickoff, `Brain::pubKickMsg` publishes
`Kick.dir = wrap(CalcKickDir - robot_theta_to_field)`. Therefore
`wrap(Kick.dir + Kick.robot_theta_to_field)` recovers the computed CalcKickDir
without rounding or changing the brain. The source includes an override for
indirect free kicks; any such trial must be identified from referee events and
excluded from this direct-shot interpretation. The measured initial state is
ordinary play (`setPlay=noSetPlay`);
later set plays must not be mistaken for that first attempt.

Fit actual travel direction by linear regression of x and y against simulation
time over the first 0.10–0.80 m of ball displacement after shot-speed movement.
Require at least three samples, stop collecting after defender contact, and
reject referee placement jumps. This gives initial launch direction before
defender deflections or boundary resets. Additional first-contact/impulse
timestamps allow later inspection of dribbling versus a clean strike.

Signed aim error is `wrap(actual_direction - CalcKickDir_at_activation)` in
degrees. Report mean and maximum **absolute** aim error, with the number of
usable directions. Also report error relative to the true ball-to-goal-center
direction at launch; the two measures answer different questions.

Goal percentage uses **all completed trials**, including failed attempts. A
goal requires a referee `goal` event. `wide` means the whole ball crosses the
opponent's end line outside the posts; `out` means another boundary. The
installed field is 14 × 9 m, with a 2.6 m goal opening and 0.11 m ball radius.
Whole-ball crossing uses the outer field-line edge, matching the referee.
`missed_contact` records failure to produce a shot in the observation window.
Keep `short` (shot stops inside the field) and `unresolved` (e.g. placement
jump before an outcome) as additional categories rather than inventing an out.

## Run

Restore cameras, bridge, and opposing referee using
`sim-multi-camera-workaround.md`. Temporarily replace the opposing referee
with the measurement fixture, then run from the host:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; nohup bash scripts/sim_kick_test_referee.sh > sim-kick-test-referee.log 2>&1 < /dev/null &'
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; source /opt/ros/humble/setup.bash; source install/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml SIM_DDS_PROFILE=/opt/booster/BoosterRos2/fastdds_profile.xml; python3 -u scripts/sim_kick_baseline.py --output .cache/kick-baseline-v0-open-play --repeats 4'
```

Use a new output directory for every run; the script will not overwrite one.
CSV and summary JSON are updated after each completed trial. Raw recordings
are under that output directory inside `/root/robocup_demo`; copy them to the
host before shutdown. The referee match is ended on completion or exceptions.
To continue after a setup interruption, rerun the same command with `--resume`.
The runner verifies the saved protocol, keeps completed results, and retries
setup up to three times per trial. It confirms discovery of `brain_node_ext`
and the localization control acknowledgment before waiting for vision
localization. Failed setup recordings are retained separately and do not enter
the completed-trial denominator.
After measurement, stop the specific `sim_kick_test_referee.py` process and
restart `sim_defender_referee.sh` to return to the frozen ordinary referee.
Do not start both referees at once.

Measurement math tests: `python3 tests/test_sim_kick_metrics.py`. They verify
known trajectory directions in all quadrants, angle wrapping, missing data,
full-ball crossing near the goal/posts/boundary, failed trials in the goal
denominator, and missing directions remaining missing rather than zero error.

Stop after the baseline report. Source attribution and behavior fixes belong
to the later requested steps and must not be silently mixed into this run.
