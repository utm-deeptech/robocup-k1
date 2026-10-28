"""Build Booster's 3v3 team tree offline (no ROS) and dump it as JSON."""
import json, os, sys
os.environ.setdefault('SOCCER_TEAM_ID', '1'); os.environ.setdefault('SOCCER_ROBOT_NAMES', 'robot1,robot2,robot3')
sys.path.insert(0, '/root/robocup_demo/agents/k1team')
sys.path.insert(1, '/opt/booster/booster_agent_data/data/agents/extract/com.k1team.soccer/libs/python-x86_64')
import py_trees
from com_booster_default3v3ai.runtime import SoccerKit
from com_booster_default3v3ai.soccer_framework import SoccerConfig
from com_booster_default3v3ai.play import PLAYBOOKS
from com_booster_default3v3ai.behavior_tree.tree import create_team_tree
kit = SoccerKit(SoccerConfig.from_env())
root, _ = create_team_tree(kit, PLAYBOOKS.create_default(kit), lambda: 0.0, None)
def walk(b):
    kind = type(b).__name__
    d = {'name': b.name, 'type': kind}
    if isinstance(b, py_trees.composites.Composite):
        d['memory'] = getattr(b, 'memory', None)
    if isinstance(b, py_trees.decorators.Decorator):
        d['children'] = [walk(b.decorated)]
    elif b.children:
        d['children'] = [walk(c) for c in b.children]
    return d
print(json.dumps(walk(root)))
