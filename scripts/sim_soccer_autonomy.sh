#!/bin/bash
# Run inside the existing virtual robot, from its copy of this repository.
set -e
cd "$(dirname "$0")/.."
export SIM_DDS_PROFILE="${SIM_DDS_PROFILE:-/opt/booster/BoosterRos2/fastdds_profile.xml}"
# Default: upstream game.xml (won the visual-kick-off comparison 12/20 vs 9/20).
# SIM_TREE=game_sim.xml selects the experimental settle/cooldown gates.
./scripts/sim_start.sh tree:="${SIM_TREE:-game.xml}" disable_com:=true
source /opt/ros/humble/setup.bash
source install/setup.bash
export FASTRTPS_DEFAULT_PROFILES_FILE="$SIM_DDS_PROFILE"
python3 -u scripts/sim_initialize_match.py "$@"
