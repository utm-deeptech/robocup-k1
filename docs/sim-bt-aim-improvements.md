# K1 behavior-tree improvements: kick aim

The simulator now has an optional, more careful striker tree. It is still Booster's BehaviorTree.CPP brain, using official vision, localization and motion skills. This change improves the checks before kicking; reliable goal aiming is still unresolved.

## What changed

The new `game_sim.xml` includes `subtree_striker_play_sim.xml`. The original game-state gates remain: autonomous control and referee PLAY are required.

The striker approaches more slowly, adjusts around the ball more gently, and pauses before activating the visual kick. Activation requires a detected ball, calibrated localization, and agreement between the desired shot direction, estimated robot heading and ball bearing within 0.12 radians (about 7 degrees). Alignment must remain valid near the ball for 500 milliseconds. Losing alignment resets that timer. A 1.5-second cooldown prevents immediate repeated kicks.

The simulator localization behavior searches within 0.20 radians of the current heading instead of the default one-degree window, and runs more frequently. Simulator-local vision-kick configuration reduces activation distance to 1 metre and angle to 0.20 radians. The visual-kick action now honors its configured maximum duration (7 seconds in this tree).

The tree decides when to start the existing Booster visual-kick motion skill. It does not directly control the foot trajectory or retrain that skill. Once started, that skill continues until its existing completion conditions or the duration limit.

Source changes are in the new XML trees, `brain_tree.h`, `brain_tree.cpp`, `locator.h`, `locator.cpp`, `utils/kick_alignment_gate.h`, and `config_local.yaml`. New scripts initialize a match and observe behavior. All are on branch `local/sim-autonomy`.

## What the live tests showed

- Original behavior: the ball went out near (6.36, -4.64), over the sideline.
- First improvement test: the ball went toward the opponent end line but missed, near (7.14, -1.62).
- Final test: logs confirmed `chase -> settle -> adjust -> settle -> auto_visual_kick`, with the alignment timer satisfied before activation. However, the first shot still went out over the sideline near (6.45, -4.64).
- The final match later recorded a home goal, score 1:0, at simulator time 2422.228 seconds after the robot chased the restarted ball. This is not evidence of consistent shot accuracy.

At the final first-kick activation, estimated heading was 0.032 radians and nearby simulator truth was 0.051 radians: heading was much closer than in the first test. But estimated robot y was -0.165 metres versus truth +0.075 metres, and estimated ball y was -0.131 versus truth 0. Thus a small estimated bearing error can still hide a meaningful lateral error. The visual-kick skill can also change direction after activation. The tests do not yet distinguish those two contributions.

Referee evidence is preserved in `docs/sim-bt-aim-evidence.json`. Detailed local logs are `sim-bt-final-world.log`, `sim-bt-final-observer.log`, `sim-bt-final-start.log`, and `.cache/sim-bt-final-brain.log`.

## Commands and checks

Build inside the existing container:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; source /opt/ros/humble/setup.bash; source install/setup.bash; CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2 colcon build --base-paths src --packages-select brain --cmake-args -Dbehaviortree_cpp_DIR=/root/robocup_demo/.cache/bt-overlay/share/behaviortree_cpp/cmake'
```

Run the new tree, reset the robot to its entrance, localize, hand over autonomous control and start the built-in referee:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; bash scripts/sim_soccer_autonomy.sh --reset-robot'
```

The brain build passed. The standalone alignment-timer test passed, covering hold duration, loss of alignment, distant-ball gating, clock rewind and invalid timestamps:

```bash
c++ -std=c++17 -Wall -Wextra -Werror -I src/brain/include tests/test_kick_alignment_gate.cpp -o .cache/test_kick_alignment_gate
.cache/test_kick_alignment_gate
```

No dependencies were installed during this enhancement. The container and Docker/GPU setup were retained. The test match was ended through the simulator referee's `/match/end` endpoint.

## Next step

Measure lateral ball-position error and the motion skill's direction throughout each kick, then correct the source of that error. Repeat center-ball shots over several matches before claiming reliable aim. Tightening the behavior-tree checks alone has not solved it.
