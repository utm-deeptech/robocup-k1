#!/bin/bash
# Copy our agent source (agents/k1team) into the container's deployed agent dir, then
# (re)start it on the given team/robots. Usage: k1team_deploy.sh [team_id] [robots] [opponents]
set -e
C=${CONTAINER:-rxlma-k1}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TEAM=${1:-1}; ROBOTS=${2:-robot1}; OPP=${3:-robot2}
E=/opt/booster/booster_agent_data/data/agents/extract/com.k1team.soccer
PKG=$E/agent/com_booster_default3v3ai/lib/python3.10/site-packages/com_booster_default3v3ai
docker exec "$C" test -d "$E" || { echo "deployed copy missing: recreate it from com.booster.default3v3ai"; exit 1; }
docker cp "$REPO/agents/k1team/com_booster_default3v3ai/." "$C:$PKG/"
docker exec "$C" find "$PKG" -name __pycache__ -prune -exec rm -rf {} +
docker cp /usr/share/booster-studio/resources/app/booster-native/statics/scripts/football3v3_runner/supervisor.py "$C":/tmp/supervisor_3v3.py
docker exec "$C" bash -lc 'killp() { for p in $(pgrep -f "$1"); do [ "$p" = "$$" ] || kill "$p" 2>/dev/null; done; }
  killp "supervisor_3v3.py com.k1team.soccer"; sleep 2; pid=$(pgrep -f booster_agent_manager_node | head -1); set -a
  while IFS= read -r -d "" kv; do case "$kv" in *=*) export "$kv";; esac; done < /proc/$pid/environ; set +a
  export SOCCER_TEAM_ID='"$TEAM"' SOCCER_ROBOT_NAMES='"$ROBOTS"' SOCCER_OPPONENT_ROBOT_NAMES='"$OPP"'; cd /tmp
  nohup python3 -u /tmp/supervisor_3v3.py com.k1team.soccer > /root/robocup_demo/sim_k1team_agent.log 2>&1 < /dev/null &
  for i in $(seq 1 40); do grep -q "=>Active" /root/robocup_demo/sim_k1team_agent.log && break; sleep 1; done
  grep -m1 "=>Active" /root/robocup_demo/sim_k1team_agent.log || { tail -20 /root/robocup_demo/sim_k1team_agent.log; exit 1; }'
