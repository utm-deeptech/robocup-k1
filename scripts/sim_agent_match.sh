#!/bin/bash
# Agent-vs-agent match: our com.k1team.soccer (team 1, robot1) vs Booster's default AI
# (team 2, robot2), fresh official referee. Loads our deeptech_pitch_K1 scene: robot1 in the
# DeepTech navy shirt, robot2 opponent. Both agents play from sim position data, so the camera relay,
# first-robot bridge and relay renderer (only our camera brain needs them) are stopped.
set -e
C=${CONTAINER:-rxlma-k1}
REPO=$(cd "$(dirname "$0")/.." && pwd)
SIM_PY=/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python
ENV='source /opt/ros/humble/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml'
[ "$(docker inspect -f '{{.State.Running}}' "$C")" = true ] || { docker start "$C"; sleep 20; }
docker exec "$C" bash -lc 'cd /root/robocup_demo; bash scripts/stop.sh >/dev/null 2>&1 || true'
echo "== no cameras"
docker exec "$C" bash -lc 'for p in $(pgrep -f "scripts/sim_(multi_camera_relay|first_robot_bridge).py"); do kill "$p"; done' || true
for p in $(pgrep -f '^/usr/share/booster-studio/.*booster-camera-renderer --physics-url ws://[0-9.]*:8790'); do kill "$p"; done
echo "== scene (robot1 in DeepTech navy, robot2 opponent)"
[ -f "$HOME/.config/Booster Studio/simulator-library/scenes/deeptech_pitch_K1.bscene" ] || python3 "$REPO/scripts/make_deeptech_scene.py"
docker cp "$REPO/scripts/sim_use_deeptech_scene.py" "$C":/root/robocup_demo/scripts/
docker exec "$C" "$SIM_PY" /root/robocup_demo/scripts/sim_use_deeptech_scene.py 2>/dev/null | tail -1
docker cp /usr/share/booster-studio/resources/app/booster-native/statics/scripts/football3v3_runner/supervisor.py "$C":/tmp/supervisor_3v3.py
echo "== referee"
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }; '"$ENV"'
  cd /root/robocup_demo; killp "python -u /root/robocup_demo/scripts/sim_defender_referee.py"; sleep 2
  GAME_CONTROL_GROUND_TRUTH_ENABLED=1 SIM_REFEREE_ALSO_JSON=1 nohup bash scripts/sim_defender_referee.sh > sim_defender_referee.log 2>&1 < /dev/null &
  for i in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:38383/health >/dev/null 2>&1 && break; sleep 1; done; sleep 3'
echo "== Booster AI (team 2)"
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }
  killp "supervisor_3v3.py com.booster.default3v3ai"; killp "launch com_booster_default3v3ai"; sleep 1; pkill -9 -f "[c]om_booster_default3v3ai/pyag"; sleep 1; pid=$(pgrep -f booster_agent_manager_node | head -1); set -a
  while IFS= read -r -d "" kv; do case "$kv" in *=*) export "$kv";; esac; done < /proc/$pid/environ; set +a
  export SOCCER_TEAM_ID=2 SOCCER_ROBOT_NAMES=robot2 SOCCER_OPPONENT_ROBOT_NAMES=robot1; cd /tmp
  nohup python3 -u /tmp/supervisor_3v3.py com.booster.default3v3ai > /root/robocup_demo/sim_opponent_agent.log 2>&1 < /dev/null &
  for i in $(seq 1 40); do grep -q "=>Active" /root/robocup_demo/sim_opponent_agent.log && break; sleep 1; done
  grep -m1 "=>Active" /root/robocup_demo/sim_opponent_agent.log'
echo "== our agent (team 1)"
# Run ours standalone: Booster's supervisor lock allows only one supervised agent per container.
docker exec "$C" mkdir -p /root/robocup_demo/agents
docker cp "$REPO/agents/k1team" "$C":/root/robocup_demo/agents/
docker cp "$REPO/scripts/k1team_run_standalone.py" "$C":/root/robocup_demo/scripts/
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }; '"$ENV"'
  killp scripts/k1team_run_standalone.py; sleep 1; cd /root/robocup_demo
  SOCCER_TEAM_ID=1 SOCCER_ROBOT_NAMES=robot1 SOCCER_OPPONENT_ROBOT_NAMES=robot2 \
    nohup python3 -u scripts/k1team_run_standalone.py > sim_k1team_agent.log 2>&1 < /dev/null &
  sleep 15; tail -5 sim_k1team_agent.log | cut -c1-200'
echo "== start"
docker exec "$C" curl -s -m 5 -X POST http://127.0.0.1:38383/match/start | head -c 200; echo
