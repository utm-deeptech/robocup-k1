# Milestone 2 progress: scene change required

Not complete. No autonomous ball approach or kick verified yet.

## Environment and scene

Build in `/root/robocup_demo` inside existing `rxlma-k1`, using a copy of the
host repository. All authored changes originate in `~/robocup_demo` on
`local/sim-autonomy`. ROS domain is 0; robot DDS profile uses loopback.
The repository builds booster_interface, booster_msgs, vision_interface and
game_controller_interface; the container also has Booster's booster_msgs overlay.

`docker inspect rxlma-k1` reports `SCENE_KEY=default_pitch_K1`.
The installed `default_pitch_K1.bscene` model has only a `pitch` geom and no
bodies. The installed `football_pitch_K1.bscene` manifest is named **Soccer
Field**, described as **Single-robot K1 soccer field**; its model includes
`goal-left`, `goal-right` and `ball` bodies. Switch to that scene in Studio's 3D
view before continuing. Simulator landmark detections are not proof of a ball.

## Changes and dependencies

- Local brain and vision YAMLs: simulator camera topics, ONNX models, team 1
  striker, three players, role switching disabled. Defaults untouched.
- `build.sh`: configurable `BUILD_WORKERS`.
- `sim_start.sh`: configurable `SIM_DDS_PROFILE`.
- `stop.sh`: target game_controller_node instead of broad process text matching.
- ONNX installer: resolve archive relative to its script, fail on errors.
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

## Build result and intended match workflow

Six packages built. Brain configuration failed because the existing
behaviortree_cpp CMake export couldn't find its library. Actual library exists
at `/opt/ros/humble/lib/x86_64-linux-gnu/libbehaviortree_cpp.so`; supply a build
search path without changing `/opt/ros`. Vision was not processed.
The existing build script prints `Build complete` even after a colcon failure;
use the colcon summary as evidence, and fix error propagation when resuming.

Simulator GameControl status: `GET http://127.0.0.1:38383/status` inside
container, currently INITIAL, team numbers 1 and 2, three players.
Official local implementation exposes `POST /match/start` to start the match
with automatic state advancement, ball/player placement and refereeing.
Do this only after the correct scene, built stack and localization are ready.
The existing game.xml already initializes control_state to 3. No behavior tree
changes made. `sim_start.sh` has not been run.

Stop for the requested GUI scene action. Then recheck container identity,
camera topics and scene; resolve the build and verify localization, ball
tracking, approach and a physical kick.
