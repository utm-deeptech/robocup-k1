# Two K1 robots with camera-based soccer

The scene retains both K1 bodies. Robot1 uses the enhanced official soccer brain. Robot2 is a stationary defender near (4.48, 0), facing the center. No second soccer brain is started.

## How the camera restriction was overcome

Booster's simulator disables its native render-model publication for more than one robot. Its renderer itself successfully loads and renders the two-robot model.

`scripts/sim_multi_camera_relay.py` reads the simulator's exported live-scene snapshot and subscribes to its live physics states. It uses Booster's own transport/model serialization classes to publish that model and its changing poses on port 8790. Booster's existing host native renderer connects to the relay and sends images to the existing camera hub. This is a rendering relay: no second physics simulation runs, and simulator poses are not supplied directly to the soccer brain. The brain continues to use the official YOLO vision output.

The relay checks robot topology, state dimensions, scene revision and state freshness. It permits short physics pauses during motion-controller reset. Scene changes require restarting it against the new snapshot. Static-body dragging without a revision change is not validated by this workflow.

The loaded native model is 205,818,550 bytes with two cameras. Renderer logs confirmed the first camera frame. ROS camera measurements at robot1's bridged original topic showed approximately 30 Hz.

`scripts/sim_first_robot_bridge.py` bridges robot1's cameras and motion RPC/state topics to the original single-player demo topic names. Robot2's locomotion requests are not bridged.

## Referee identity

The simulator assigns the second attached body the name robot2 regardless of the requested robot4 name. Its default roster lists robot2 as a teammate. We replaced only the built-in referee worker with the same official GameControl implementation, a live physics connection, and explicit rosters:

- Home/team 1: robot1 player 1; absent roster slots robot3 and robot5.
- Away/team 2: robot2 player 1; absent roster slots robot4 and robot6.

`scripts/sim_defender_referee.py` attaches the official service to the live physics client. `sim_defender_referee.sh` stops the previous referee worker and starts it with those settings. This retains three players per team in the protocol while the scene contains two bodies.

## Commands used

Start the relay inside the existing container:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; nohup /usr/local/booster_robot/booster_robocup_sim/.venv/bin/python -u scripts/sim_multi_camera_relay.py > sim_multi_camera_relay.log 2>&1 < /dev/null &'
```

Connect the host renderer to the relay, using its current PID (64227 was the replacement PID; the command used the previous PID 61357):

```bash
python3 scripts/sim_restart_camera_renderer.py 61357 --physics-url ws://172.17.0.2:8790
```

The address is the current container IP, verified using:

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' rxlma-k1
```

Start the first-robot bridge after sourcing ROS and the repo overlay:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; source /opt/ros/humble/setup.bash; source install/setup.bash; nohup python3 -u scripts/sim_first_robot_bridge.py > sim_first_robot_bridge.log 2>&1 < /dev/null &'
```

Start the corrected official referee:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; nohup bash scripts/sim_defender_referee.sh > sim_defender_referee.log 2>&1 < /dev/null &'
```

With those services running, restart the enhanced demo using:

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; bash scripts/sim_soccer_autonomy.sh --reset-robot'
```

The live scene and container were preserved. Installed simulator and ROS files were unchanged; no dependencies were installed. All authored helpers are in the repo on `local/sim-autonomy`.

## Evidence and limits

Logs: `sim-camera-renderer.log` on the host; `sim_multi_camera_relay.log`, `sim_first_robot_bridge.log`, `sim_defender_referee.log` inside `/root/robocup_demo`; referee events inside `/root/robocup_demo/.cache/defender-referee/events.jsonl`. Physics observations are recorded in host `sim-defender-roster-world.log`.

The scene uses two robot bodies and one active soccer brain. Robot2 is a standing physical defender, not an autonomous player. Two cameras were tested; larger robot counts and avoidance/shot planning around defenders are not yet validated. The earlier single-robot report still applies to kick-aim limitations.

## Live validation results

The corrected referee entered PLAY at simulator time 1842.528. Brain logs showed `settle -> auto_visual_kick` with stable alignment and later exercised the 7-second kick duration limit. The referee recorded a robot1 ball touch at simulator time 1860.160. Physics observations showed the ball moved to approximately (0.798, -0.417) while robot2 remained at (4.479, 0), upright. This is evidence of live play and ball contact with two bodies present; it is not evidence of an accurate shot or successful goal. Later in that test, robot1 wandered and was penalized, so the behavior still needs work.

A separate render-pose check reconstructed both robot positions from the exported model and live joint state and matched the simulator world positions (within sampling precision). The relay also applies the same collision-geometry visibility and color preparation as the installed physics process.

The match initializer now releases any previous referee body hold before resetting robot1. A fresh run then localized at approximately (-5.082, 4.986, -88.023 degrees) and entered READY. It was left running for the user to watch. Referee evidence from the completed validation is in `docs/sim-multi-robot-evidence.json`.
