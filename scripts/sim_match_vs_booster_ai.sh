#!/bin/bash
# Local test fixture: 1v1 match of our brain (robot1, team 1) vs Booster's default 3v3 AI
# (robot2, team 2) under Booster's official referee. Run on the HOST with Booster Studio open
# and the K1 3D view showing (its camera renderer must be running).
# Nothing here modifies Booster's referee or simulator; see docs/k1-soccer-strategy.
set -e
C=${CONTAINER:-rxlma-k1}
REPO=$(cd "$(dirname "$0")/.." && pwd)
SIM_PY=/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python
# Kill matching processes except this shell (its own command line contains the pattern).
KILLP='killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }; '
ENV='source /opt/ros/humble/setup.bash; source /root/robocup_demo/install/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml'
step() { echo "== $*"; }

# Studio's own renderer reads physics directly; one we redirected earlier reads the relay (:8790).
RENDERER='^/usr/share/booster-studio/.*booster-camera-renderer --physics-url'
studio_renderer=$(pgrep -n -f "$RENDERER ws://127.0.0.1:" || true)
relay_renderer=$(pgrep -n -f "$RENDERER ws://[0-9.]*:8790" || true)
[ -n "$studio_renderer$relay_renderer" ] || { echo "No camera renderer: open Booster Studio and the K1 3D view first"; exit 1; }

step "robots"
docker exec "$C" "$SIM_PY" /root/robocup_demo/scripts/sim_add_opponent.py --x 4.5 --y 0 >/dev/null 2>&1
sleep 5

step "camera relay"
docker exec "$C" bash -lc "$KILLP"'cd /root/robocup_demo; killp sim_multi_camera_relay.py; sleep 1
  nohup '"$SIM_PY"' -u scripts/sim_multi_camera_relay.py > sim_multi_camera_relay.log 2>&1 < /dev/null &
  for i in $(seq 1 60); do grep -q "Relay ready" sim_multi_camera_relay.log && break; sleep 1; done; grep "Relay ready" sim_multi_camera_relay.log'
ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$C")
if [ -n "$studio_renderer" ]; then
  # Fresh Studio renderer (first run, or Studio restarted): retire stale relay renderers, redirect it.
  for p in $(pgrep -f "$RENDERER ws://[0-9.]*:8790"); do kill "$p"; done
  python3 "$REPO/scripts/sim_restart_camera_renderer.py" "$studio_renderer" --physics-url "ws://$ip:8790"
else
  echo "renderer $relay_renderer already reads the relay"
fi

step "first-robot bridge"
docker exec "$C" bash -lc "$KILLP$ENV"'; cd /root/robocup_demo; killp sim_first_robot_bridge.py; sleep 1
  nohup python3 -u scripts/sim_first_robot_bridge.py > sim_first_robot_bridge.log 2>&1 < /dev/null & sleep 8
  timeout 10 ros2 topic hz /rgbd_camera/rgb/image_compressed 2>&1 | grep -m1 "average rate"'

step "referee (official GameControl, explicit roster, JSON mirror for the Booster AI)"
docker exec "$C" bash -lc "$KILLP$ENV"'; cd /root/robocup_demo; killp "python -u /root/robocup_demo/scripts/sim_defender_referee.py"; sleep 2
  GAME_CONTROL_GROUND_TRUTH_ENABLED=1 SIM_REFEREE_ALSO_JSON=1 nohup bash scripts/sim_defender_referee.sh > sim_defender_referee.log 2>&1 < /dev/null & sleep 15
  ros2 topic info /soccer/game_controller | grep -m1 "Publisher count"'

step "Booster default AI on robot2"
docker cp /usr/share/booster-studio/resources/app/booster-native/statics/scripts/football3v3_runner/supervisor.py "$C":/tmp/supervisor_3v3.py
docker exec "$C" bash -lc "$KILLP"'killp supervisor_3v3.py; sleep 1; pid=$(pgrep -f booster_agent_manager_node | head -1); set -a
  while IFS= read -r -d "" kv; do case "$kv" in *=*) export "$kv";; esac; done < /proc/$pid/environ; set +a
  export SOCCER_TEAM_ID=2 SOCCER_ROBOT_NAMES=robot2 SOCCER_OPPONENT_ROBOT_NAMES=robot1; cd /tmp
  nohup python3 -u /tmp/supervisor_3v3.py com.booster.default3v3ai > /root/robocup_demo/sim_opponent_agent.log 2>&1 < /dev/null &
  for i in $(seq 1 40); do grep -q "=>Active" /root/robocup_demo/sim_opponent_agent.log && break; sleep 1; done; grep -m1 "=>Active" /root/robocup_demo/sim_opponent_agent.log'

step "our brain (retries: the initial soccer-mode switch sometimes times out)"
for i in 1 2 3 4; do
  out=$(docker exec "$C" bash -lc 'cd /root/robocup_demo; bash scripts/stop.sh >/dev/null 2>&1; sleep 2; timeout 150 bash scripts/sim_soccer_autonomy.sh --reset-robot' 2>&1 || true)
  echo "$out" | grep -q '"match_started"' && { echo "$out" | grep '^{"stage'; exit 0; }
  echo "attempt $i failed: $(echo "$out" | grep -E 'Error|failed' | tail -1)"
done
exit 1
