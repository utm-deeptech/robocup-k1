# Two K1 robots with camera-based soccer

## Frozen version and restart from a stopped setup

The reproducible code checkpoint is the annotated tag `v0-two-robot-working`
on `local/sim-autonomy`. `docs/two-robot-freeze.json` records the original
validated commit, image, Studio version, and SHA-256 of the local configs,
tree, and models. The tag freezes source and configuration, not live processes
or a Docker image. The existing container retains the installed dependencies.

On 2026-10-12 the container was initially stopped. Starting it restored the
soccer field and center ball with **only robot1**. Live scene edits, the defender,
camera relay, bridge, and replacement referee must be restored after a restart.
Do not assume the previous two-robot scene survives shutdown.

These instructions restart the frozen setup using the existing configured host
and container. They do not recreate the container or reinstall Docker/NVIDIA.
Dependency installation and the full build commands are recorded in
`sim-soccer-progress.md` if the existing build is unavailable.

1. On the host, verify the branch and container identity:

   ```bash
   cd /home/anas-alanqar/robocup_demo
   git status --short --branch
   git log -1 --oneline v0-two-robot-working
   docker ps -a --format '{{.Names}} {{.Status}}'
   docker start rxlma-k1
   ```

   Use the actual existing container name if Studio renamed it. Do not delete
   or recreate it. For a later restore, inspect any uncommitted changes before
   choosing to check out the tag; do not discard work to restore it.

2. **GUI prerequisite:** open Booster Studio, select the existing K1 virtual
   robot, and open its 3D view. Confirm the soccer field and ball are visible.
   The agent must stop and ask the user before this GUI step. If the scene is
   different, stop and agree on a scene change; do not infer it from a saved
   scene name. Studio starts the host native camera renderer and its camera
   connection. Find it on the host:

   ```bash
   pgrep -af booster-camera-renderer
   ```

   If no actual renderer process is listed, do not start soccer. Opening
   Studio is needed before the renderer restart helper can preserve its
   arguments and environment. Ignore the search command itself if listed.

3. Synchronize the authored source into the existing container, preserving its
   `build/`, `install/`, and `.cache/` directories. On the host:

   ```bash
   docker cp scripts/. rxlma-k1:/root/robocup_demo/scripts/
   docker cp src/. rxlma-k1:/root/robocup_demo/src/
   docker cp docs/. rxlma-k1:/root/robocup_demo/docs/
   docker cp configs/. rxlma-k1:/root/robocup_demo/configs/
   ```

   Source changes after the frozen tag need a rebuild; for the unchanged
   checkpoint, the existing build can be reused. Verify the local YAMLs and
   ONNX models against `two-robot-freeze.json`. If rebuilding is needed:

   ```bash
   docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; bash scripts/sim_prepare_bt_overlay.sh; export BUILD_WORKERS=2 CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2; ./scripts/build_no_cuda.sh -Dbehaviortree_cpp_DIR=/root/robocup_demo/.cache/bt-overlay/share/behaviortree_cpp/cmake'
   ```

4. Reattach the stationary defender. This helper is idempotent when a second
   robot is already present; verify its identity and pose in that case:

   ```bash
   docker exec rxlma-k1 /usr/local/booster_robot/booster_robocup_sim/.venv/bin/python /root/robocup_demo/scripts/sim_add_opponent.py --x 4.5 --y 0
   docker exec rxlma-k1 /usr/local/booster_robot/booster_robocup_sim/.venv/bin/python /root/robocup_demo/scripts/sim_world_probe.py --seconds 3
   ```

   Expect robot1 and robot2, with robot2 upright near `(4.48, 0)` and heading
   approximately pi. Attaching restarts motion controls and changes ROS topics.

5. Start the relay and first-robot bridge using the commands below. First inspect
   existing processes with `docker exec rxlma-k1 ps -eo pid,comm,args`.
   Start each helper only if absent; do not create duplicate publishers. If a
   relay from an earlier scene revision is running, stop that specific helper
   PID and restart it after attachment. Read its log and require `Relay ready`
   with two robots and two cameras before connecting the renderer.

6. Read the current container IP using the command below. Run
   `sim_restart_camera_renderer.py` with the **current** renderer PID and
   `ws://CURRENT_CONTAINER_IP:8790`; the old PIDs and IPs in the historical
   commands are examples, not constants. Container restart can also remap the
   camera hub's host port. Inspect `docker port rxlma-k1 9876/tcp` before reusing
   the renderer's camera URL. If it is stale, add
   `--camera-publish-url ws://CURRENT_CONTAINER_IP:9876/publish` when restarting
   the renderer (or use the current mapped host port). Verify real images arrive.
   If Studio creates multiple renderer instances, identify the one
   for this virtual robot by its command arguments before restarting it.

7. Start the corrected referee using the command below. Its helper stops the
   previous referee worker and assigns robot2 to team 2. Check
   `/root/robocup_demo/sim_defender_referee.log` for successful startup.

8. Check that real camera messages arrive through the bridge before starting
   the brain. A topic publisher count alone is insufficient because the bridge
   can advertise an empty output:

   ```bash
   docker exec rxlma-k1 bash -lc 'source /opt/ros/humble/setup.bash; source /root/robocup_demo/install/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml; timeout 15 ros2 topic hz /rgbd_camera/rgb/image_compressed'
   ```

   Expect approximately 30 Hz. The timeout deliberately exits after the
   measurement. Also check depth messages on `/rgbd_camera/depth/image_raw`.
   If no samples arrive, stop and inspect relay/renderer/bridge logs.

9. Run `sim_soccer_autonomy.sh --reset-robot` using the command below. It launches
   the enhanced `game_sim.xml`, resets only robot1, releases any referee hold,
   selects soccer mode, requests vision-based localization, and hands over to
   the referee only after a `Locate Success` message. Require successful
   localization and READY → SET → PLAY before reporting play restored.

   Monitor `brain.log`, `vision.log`, `game_controller.log`, the world probe,
   and `.cache/defender-referee/events.jsonl`. Verify robot2 stays in place and
   robot1 contacts the ball; this does not establish shot accuracy.

The camera relay and referee wrapper are local testing infrastructure. They
are not part of a future submitted match agent. No agent decision may consume
the test observer's ground truth.

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
