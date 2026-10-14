#!/bin/bash
# Agent-vs-agent match: our com.k1team.soccer (team 1, robot1) vs Booster's default AI
# (team 2, robot2), fresh official referee. Needs the two-robot scene from
# sim_match_vs_booster_ai.sh (robots attached). Our camera brain must not be running.
set -e
C=${CONTAINER:-rxlma-k1}
REPO=$(cd "$(dirname "$0")/.." && pwd)
ENV='source /opt/ros/humble/setup.bash; export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/booster/BoosterRos2/fastdds_profile.xml'
docker exec "$C" bash -lc 'cd /root/robocup_demo; bash scripts/stop.sh >/dev/null 2>&1 || true'
echo "== referee"
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }; '"$ENV"'
  cd /root/robocup_demo; killp "python -u /root/robocup_demo/scripts/sim_defender_referee.py"; sleep 2
  GAME_CONTROL_GROUND_TRUTH_ENABLED=1 SIM_REFEREE_ALSO_JSON=1 nohup bash scripts/sim_defender_referee.sh > sim_defender_referee.log 2>&1 < /dev/null &
  for i in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:38383/health >/dev/null 2>&1 && break; sleep 1; done; sleep 3'
echo "== Booster AI (team 2)"
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }
  killp "supervisor_3v3.py com.booster.default3v3ai"; sleep 2; pid=$(pgrep -f booster_agent_manager_node | head -1); set -a
  while IFS= read -r -d "" kv; do case "$kv" in *=*) export "$kv";; esac; done < /proc/$pid/environ; set +a
  export SOCCER_TEAM_ID=2 SOCCER_ROBOT_NAMES=robot2 SOCCER_OPPONENT_ROBOT_NAMES=robot1; cd /tmp
  nohup python3 -u /tmp/supervisor_3v3.py com.booster.default3v3ai > /root/robocup_demo/sim_opponent_agent.log 2>&1 < /dev/null &
  for i in $(seq 1 40); do grep -q "=>Active" /root/robocup_demo/sim_opponent_agent.log && break; sleep 1; done
  grep -m1 "=>Active" /root/robocup_demo/sim_opponent_agent.log'
echo "== our agent (team 1)"
bash "$REPO/scripts/k1team_deploy.sh" 1 robot1 robot2
echo "== start"
docker exec "$C" curl -s -m 5 -X POST http://127.0.0.1:38383/match/start | head -c 200; echo
