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
# A CANCEL (LT+X) reaches the brain after each referee kickoff transition; hand control back.
# SIM_PLAY_HANDOVER=0 disables it. Auto-recovery from freezes is experimental and off
# (it looped on restarts under the Studio referee); run the watcher without --no-recovery to try it.
if [ "${SIM_PLAY_HANDOVER:-1}" != 0 ]; then
    nohup python3 -u scripts/sim_play_handover.py --no-recovery > sim_play_handover.log 2>&1 < /dev/null &
fi
python3 -u scripts/sim_initialize_match.py "$@"
