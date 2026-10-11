# Milestone 2: autonomous approach and kick verified

Completed on 2026-10-11. The official vision, brain and GameController stack
localized the K1, found the ball, walked to it and activated RLVisionKick.
The automatic referee recorded robot1 touching the ball at sim time 1021.512 s.
The ball then moved from (0, 0) to (6.363, -4.639) m. This was a kick toward
the sideline, not a scored goal. See `sim-soccer-evidence.json`.

## Environment and scene

Build in `/root/robocup_demo` inside existing `rxlma-k1`, using a copy of the
host repository. All authored changes originate in `~/robocup_demo` on
`local/sim-autonomy`. ROS domain is 0; robot DDS profile uses loopback.
The repository builds booster_interface, booster_msgs, vision_interface and
game_controller_interface; the container also has Booster's booster_msgs overlay.

The live robot camera shows a soccer field and goal. The installed scene archive
and container's initial SCENE_KEY are insufficient to identify the live scene:
my earlier statement that the scene had no ball was incorrect. A read-only
subscription through the simulator's installed PhysicsWebSocketClient confirmed
ballBodyId=3 and ballPosition=(0, 0, 0.1099). No scene change was required.

## Changes and dependencies

- Local brain and vision YAMLs: simulator camera topics, ONNX models, team 1
  striker, three players, role switching disabled. Defaults untouched.
- `build.sh`: configurable `BUILD_WORKERS`.
- `sim_start.sh`: configurable `SIM_DDS_PROFILE`.
- `stop.sh`: target game_controller_node instead of broad process text matching.
- ONNX installer: resolve archive relative to its script, fail on errors.
- build.sh/build_no_cuda.sh: propagate failures; pass extra CMake options.
- sim_prepare_bt_overlay.sh: repo-local copy of BehaviorTree CMake exports and
  links to existing library/header paths. No writes under /opt/ros.
- GameController launch: sim=true disables its fixed referee IP whitelist.
  Real-robot default remains unchanged.
- sim_world_probe.py: read-only live physics subscription for ball/robot evidence.
- Fetched ONNX models and ONNX Runtime archive from the branch's official GitHub
  LFS media URLs; verified size and SHA-256 against existing pointers.
- Installed in container via apt: git-lfs, libopencv-dev, libpcl-dev,
  libasound2-dev, libfftw3-dev and their apt dependencies. Full apt output is in
  host `sim-dependencies.log` (ignored by Git). backward_ros already existed.
- Installed ONNX Runtime C++ 1.23.2 headers/libraries under `/usr/local`.
- Copied missing official C++ SDK headers and static library under `/usr/local`
  from https://github.com/BoosterRobotics/booster_robotics_sdk, cloned in host
  `.cache/booster_robotics_sdk`. Did not reinstall the existing Python SDK.
- Host sudo is password protected. No host apt packages installed; container's
  git-lfs binary copied to `.cache/git-lfs`, with repository-local LFS filters.

## Commands executed

```bash
docker exec rxlma-k1 bash -lc 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y git-lfs libopencv-dev libpcl-dev libasound2-dev libfftw3-dev' > ~/robocup_demo/sim-dependencies.log 2>&1
git clone --depth 1 https://github.com/BoosterRobotics/booster_robotics_sdk.git ~/robocup_demo/.cache/booster_robotics_sdk
docker cp ~/robocup_demo rxlma-k1:/root/robocup_demo
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; ./third_party/install_onnxruntime.sh; cp -r .cache/booster_robotics_sdk/include/* /usr/local/include/; cp .cache/booster_robotics_sdk/lib/x86_64/libbooster_robotics_sdk.a /usr/local/lib/; ldconfig'
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; export BUILD_WORKERS=2 CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2; ./scripts/build_no_cuda.sh' > ~/robocup_demo/sim-build.log 2>&1
```

## Build and run commands that succeeded

```bash
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; bash scripts/sim_prepare_bt_overlay.sh; export BUILD_WORKERS=2 CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2; ./scripts/build_no_cuda.sh -Dbehaviortree_cpp_DIR=/root/robocup_demo/.cache/bt-overlay/share/behaviortree_cpp/cmake'
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; SIM_DDS_PROFILE=/opt/booster/BoosterRos2/fastdds_profile.xml ./scripts/sim_start.sh disable_com:=true'
```

All nine packages built (2 min 9 s). Remaining build diagnostics were warnings,
including an existing possibly uninitialized markerType. No behavior tree edits.
The referee initially rejected simulator packets due to a fixed whitelist;
after fixing launch.py, game_controller was rebuilt with
`colcon build --base-paths src --packages-select game_controller` and relaunched
with `ros2 launch game_controller launch.py sim:=true`.

## Initialization and match start

The smoke test had moved the robot away from the entrance pose expected by
SelfLocateEnterField. Returned only robot1 to its initial scene pose using the
installed official simulator transport (no container reset/recreation):

```bash
docker exec -i rxlma-k1 bash -lc 'cd /usr/local/booster_robot/booster_robocup_sim; .venv/bin/python -' <<'PYRESET'
import time
from core.physics_transport import PhysicsTransportConfig, PhysicsCommand
from transport.websocket.physics_ws import PhysicsWebSocketClient
c = PhysicsWebSocketClient(PhysicsTransportConfig(port=8788), owner='soccer-initial-placement')
c.connect()
time.sleep(1)
c.send_command(PhysicsCommand.RESET_ROBOT, {'robot_name': 'robot1'})
time.sleep(3)
c.disconnect()
PYRESET
```

Sent the README's LT+A localization and LT+B handover controls from code.
A single CLI publication did not reliably reach the brain; repeated 10 Hz
publications worked. These timeout commands intentionally exit 124 after their
publication window. Source ROS and the built overlay first, and use the same DDS
profile as the launch:

```bash
source /opt/ros/humble/setup.bash
source /root/robocup_demo/install/setup.bash
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml
timeout 5 ros2 topic pub -r 10 /remote_controller_state booster_interface/msg/RemoteControllerState '{lt: true, a: true}'
```

Brain logged `Locate Success: -5.007338 5.005214 -94.524406`.
Ground truth was `(-4.999972, 4.981805, -1.569975 rad)`.
After the simulator reset returned the motion controller to PREP, explicitly
requested soccer mode through the installed SDK:

```bash
docker exec -i rxlma-k1 python3 - <<'PYSDK'
import booster_robotics_sdk_python as b
b.ChannelFactory.Instance().Init(0, 'lo')
c = b.B1LocoClient()
c.Init()
c.ChangeMode(b.RobotMode.kSoccer)
PYSDK
```

Then sent LT+B using the same sourced environment:

```bash
timeout 3 ros2 topic pub -r 10 /remote_controller_state booster_interface/msg/RemoteControllerState '{lt: true, b: true}'
```

Started the intended built-in referee workflow:

```bash
docker exec -i rxlma-k1 python3 - <<'PYMATCH'
import urllib.request
req = urllib.request.Request('http://127.0.0.1:38383/match/start', data=b'', method='POST')
print(urllib.request.urlopen(req, timeout=5).read().decode())
PYMATCH
docker exec rxlma-k1 bash -lc 'cd /root/robocup_demo; /usr/local/booster_robot/booster_robocup_sim/.venv/bin/python scripts/sim_world_probe.py --seconds 60'
```

The automatic referee advanced READY -> SET -> PLAY. ControlState was 3 and
role striker. No human joystick input, scripted ball approach or manual kick:
the behavior tree selected motion and RLVisionKick itself.

## Evidence and limits

- ONNX inference ran on live 320x240 camera frames and published ball and field
  detections to /booster_soccer/detection.
- Brain localization agreed with ground truth at initialization (about 2.5 cm
  position error and 4.6 degrees heading error).
- Robot moved from about (-5, 5) through the READY position near (-2, 0), then
  approached the center ball during PLAY.
- Brain issued RLVisionKick(start=true), then start=false.
- Referee event local-match:7 identified a ball_touch by home robot1, player1,
  at sim time 1021.512 s. Event local-match:8 released kickoff restrictions.
- Ball was stationary at (0, 0) before contact and reached (6.363, -4.639) m
  afterward. Referee recorded lastTouchSide=home and an opponent throw-in.

The kick missed the goal. Later localization/aim accuracy and ongoing play
against absent opponents remain unverified. The stack and referee were left
running at the milestone report; no further tuning was performed. Next work,
if requested, is calibrating camera geometry/odometry and improving kick aim.

Host logs: sim-build.log, sim-dependencies.log, sim-match-world.log (Git ignored).
Container logs: /root/robocup_demo/{brain,vision,game_controller}.log and
/usr/local/booster_robot/booster_robocup_sim/logs/game-control/events.jsonl.
