#!/bin/bash
# Launch the pinned upstream brain overlay for measurement, preserving sim I/O.
set -e
cd "$(dirname "$0")/.."
bash scripts/stop.sh || true
source /opt/ros/humble/setup.bash
source install/setup.bash
source "${SIM_UPSTREAM_OVERLAY:-.cache/upstream-ab}/install/setup.bash"
export FASTRTPS_DEFAULT_PROFILES_FILE="${SIM_DDS_PROFILE:-/opt/booster/BoosterRos2/fastdds_profile.xml}"
nohup ros2 launch vision launch.py sim:=true > vision.log 2>&1 < /dev/null &
nohup ros2 launch brain launch.py sim:=true tree:=game.xml disable_com:=true \
    vision_config_path:="$PWD/install/vision/share/vision/config" > brain.log 2>&1 < /dev/null &
nohup ros2 launch game_controller launch.py sim:=true > game_controller.log 2>&1 < /dev/null &
