#!/usr/bin/env python3
"""Convert a py_trees JSON dump (scripts/... dump_bt output) into an Excalidraw file.

Usage: bt_to_excalidraw.py bt.json out.excalidraw
Repeated per-player subtrees (2), (3) are collapsed to one note each.
"""
import json
import random
import re
import sys
import textwrap

COMPOSITE = {
    'Sequence': ('→ ', '#a5d8ff'),
    'Selector': ('? ', '#ffd8a8'),
    'Parallel': ('⇉ ', '#d0bfff'),
}
DECORATOR = ('◇ ', '#dee2e6')
CONDITION = ('', '#b2f2bb')
ACTION = ('', '#fff3bf')
NOTE = ('', '#f1f3f5')
W, DX, GAP = 300, 380, 18
NAME_FONT, DESC_FONT, WRAP = 14, 12, 40

# Plain-language description per node, keyed by name without the "(player)" suffix.
# Nodes whose meaning depends on the role branch they sit in are keyed "<Role>/<name>".
DESC = {
    'TeamRoot': 'Root. Runs once per control cycle for the whole team: read data, decide, apply safety, send commands.',
    'DataLayer': 'Refresh everything the decisions read this tick. Always succeeds.',
    'UpdateClock': 'Store the current time and clear last tick\'s "safety stop active" flag.',
    'UpdatePlayContext': 'Take a snapshot of the world: game state, ball, teammates and opponents.',
    'UpdateGameState': 'Drop the referee state if it is older than 2.0 s, so stale data is never used.',
    'UpdateRecentBall': 'Forget the ball if it was last seen more than 1.5 s ago.',
    'UpdateRobotPoses': 'Forget any teammate or opponent pose older than 2.0 s.',
    'UpdateRobotStatus': 'Read this robot\'s hardware status: fallen or not, current mode (walk or other).',
    'MatchControl': 'Pick ONE behaviour for the team: the first branch (top to bottom) that succeeds wins.',
    'SafetyGuards': 'Global stop checks. If any matches, the whole team stands still this tick.',
    'NoGameStop': 'No referee data received: stop everyone.',
    '¬HasGameState': 'Inverter: true when there is NO game-controller state.',
    'HasGameState': 'Is there a fresh referee (game-controller) state?',
    'StopAll(no game controller state)': 'Send stop to all 3 robots and mark safety as active.',
    'AllInactiveStop': 'Every one of our players is penalised or missing: stop everyone.',
    'IsAllPlayersInactive': 'True if none of our robots is allowed to play right now.',
    'StopAll(all players inactive)': 'Send stop to all 3 robots.',
    'NonPlayingStop': 'Game is in INITIAL, SET, FINISHED or a timeout: stop everyone.',
    'IsNonPlayingState': 'True in INITIAL / SET / FINISHED states or during a timeout.',
    'StopAll(non playing state)': 'Send stop to all 3 robots (robots must not move in these states).',
    'ReadyPhase': 'READY state: every robot walks to its legal kickoff position.',
    'IsGameInState(READY)': 'Is the referee state READY?',
    'ReadySlots': 'Runs all 3 robots at the same time, one branch each.',
    'GoReadyTarget': 'Walk to this robot\'s slot position (CENTER / SIDE / KEEPER), avoiding opponents.',
    'PlayingPhase': 'PLAYING state: the actual football.',
    'IsGameInState(PLAYING)': 'Is the referee state PLAYING?',
    'PlaybookCore': 'Assign roles, then let every robot act on its role.',
    'AssignRoles': 'Keeper = fixed keeper slot. Chaser = best-scored robot near the ball (keeper only if ball is in our defensive area). Rest = supporters. No ball seen = no roles.',
    'Roles': 'Runs all 3 robots at the same time, one subtree each.',
    'Player': 'This robot\'s decision: first branch that succeeds wins (restart rules first, then its role).',
    'KickoffHold': 'Opponent kickoff still running: stay in the ready position.',
    'IsOpponentKickoffActive': 'True while the opponent\'s kickoff time is still running.',
    'PenaltyAvoid': 'Opponent free kick / restart: keep the required distance from the ball.',
    'IsOpponentRestartActive': 'True during an opponent restart (free kick, corner, goal kick...).',
    'AvoidOpponentRestart': 'If closer than 1.6 m to the ball (rule: 1.45 m), walk to a legal spot; otherwise stand still.',
    'PenaltyStopped': 'Referee has stopped play: this robot stops.',
    'IsGameStopped': 'True when the referee has paused/stopped the game.',
    'StopPlayer': 'Send a stop command to this robot only.',
    'AsChaser': 'This robot is the CHASER: go to the ball and kick it.',
    'IsRole<chaser>': 'Did AssignRoles make this robot the chaser?',
    'Chaser/Attack': 'Kick if close enough, otherwise walk to the ball.',
    'Chaser/KickBranch': 'Kick only when inside kick range.',
    'Chaser/IsInKickRange': 'Ball closer than 2.5 m (stays true until > 3.0 m for 1.5 s, to avoid flicker).',
    'Chaser/KickAction': 'Kick toward the target (power 1.5). CENTER robot shoots at goal; SIDE robot clears or passes.',
    'Chaser/MoveToTarget': 'Walk to a point 0.4 m behind the ball, lined up with the kick direction.',
    'AsSupporter': 'This robot is a SUPPORTER: hold a helpful position, never kick.',
    'IsRole<supporter>': 'Did AssignRoles make this robot a supporter?',
    'Supporter/MoveToTarget': 'Walk to the support position (behind / beside the chaser) and face the ball.',
    'AsGoalkeeper': 'This robot is the GOALKEEPER: guard the goal, clear dangerous balls.',
    'IsRole<goalkeeper>': 'Is this robot the goalkeeper?',
    'Goalkeeper/Attack': 'Clear the ball if it is dangerous and close, otherwise guard.',
    'Goalkeeper/KickBranch': 'Clear only when the ball is dangerous AND in kick range.',
    'Goalkeeper/IsKickWanted': 'Is the ball inside our own defensive area?',
    'Goalkeeper/IsInKickRange': 'Ball closer than 2.5 m (until > 3.0 m for 1.5 s).',
    'Goalkeeper/KickAction': 'Clear the ball toward the opponent goal (or back in-field if near the sideline).',
    'Goalkeeper/MoveToTarget': 'Ball dangerous: go 0.22 m behind it. Otherwise: stand on the goal line, between ball and goal.',
    'WaitForBall': 'Fallback when no ball is seen or no role assigned: stand still and wait.',
    'StopAll(unsupported state)': 'Last resort if nothing above matched: stop everyone.',
    'SafetyOverrides': 'Runs AFTER the decision for all 3 robots: may overwrite a robot\'s command for safety.',
    'PlayerSafety': 'Safety checks for one robot, in order: allowed? fallen? walk mode?',
    'AllowedGuard': 'Stop this robot if it is penalised or missing (unless the whole team is already stopped).',
    'IsGlobalSafetyActive': 'True if a team-wide StopAll already ran this tick (nothing more to do).',
    'AllowedStop': 'Penalised / inactive robot: force stop.',
    'IsPlayerDisallowed': 'True if the referee has penalised this robot or it is not on the field.',
    'AllowedOk': 'Always succeeds: robot is allowed, keep its command.',
    'FallDownGuard': 'If the robot fell, make it get up.',
    'FallDownRecovery': 'Fallen: trigger get-up and stop walking.',
    'IsRobotFallen': 'True if the robot\'s status says it has fallen.',
    'TriggerGetUp': 'Ask the robot to stand up (retries are throttled).',
    'FallDownOk': 'Always succeeds: robot is standing.',
    'WalkModeGuard': 'Make sure the robot is in walk mode when it has to move or kick.',
    'WalkModeRecovery': 'Not in walk mode but needs to move: switch it.',
    'IsNotWalkMode': 'True if the robot is not in walk mode.',
    'IsWalkModeRequired': 'True if this tick\'s command moves or kicks (stop does not need walk mode).',
    'TriggerEnterWalkMode': 'Request the switch to walk mode (takes effect next tick).',
    'WalkModeOk': 'Always succeeds: nothing to fix.',
    'CommitTeamCommands': 'Collect the 3 final commands (stop for any missing) and send them to the robots.',
}


def describe(node, role):
    name = re.sub(r'\((\d)\)$', '', node['name'])
    if node['type'] == 'Note':
        return 'Identical to player 1\'s subtree, only the player number differs.'
    return DESC.get(f'{role}/{name}') or DESC.get(name) or DESC.get(node['name'], '')


def label_of(node, role):
    prefix, _ = style(node)
    lines = [prefix + node['name']]
    desc = describe(node, role)
    if desc:
        lines += [''] + textwrap.wrap(desc, WRAP)
    return '\n'.join(lines)


def box_height(label):
    return 16 + label.count('\n') * DESC_FONT * 1.25 + NAME_FONT * 1.25


def style(node):
    t = node['type']
    if t in COMPOSITE:
        return COMPOSITE[t]
    if t == 'Inverter' or node['name'].startswith('¬'):
        return DECORATOR
    if t.startswith(('Is', 'Has')):
        return CONDITION
    if t == 'Note':
        return NOTE
    return ACTION


def collapse(node):
    kids = []
    for c in node.get('children', []):
        name = c['name']
        if (name.startswith(('Player(', 'PlayerSafety(')) and not name.endswith('(1)')):
            kids.append({'name': f'{name}: same subtree as ({1})', 'type': 'Note'})
        else:
            kids.append(collapse(c))
    out = dict(node)
    if kids:
        out['children'] = kids
    return out


ROLE_OF = {'AsChaser': 'Chaser', 'AsSupporter': 'Supporter', 'AsGoalkeeper': 'Goalkeeper'}


def layout(node, depth=0, cursor=None, role=''):
    cursor = cursor if cursor is not None else [0.0]
    role = ROLE_OF.get(re.sub(r'\(\d\)$', '', node['name']), role)
    node['_label'] = label_of(node, role)
    node['_h'] = box_height(node['_label'])
    kids = node.get('children', [])
    for c in kids:
        layout(c, depth + 1, cursor, role)
    if kids:
        mid = (kids[0]['_y'] + kids[0]['_h'] / 2 + kids[-1]['_y'] + kids[-1]['_h'] / 2) / 2
        node['_y'] = mid - node['_h'] / 2
    else:
        node['_y'] = cursor[0]
        cursor[0] += node['_h'] + GAP
    node['_x'] = depth * DX
    return node


def base(kind, eid, x, y, w, h, **kw):
    e = dict(id=eid, type=kind, x=x, y=y, width=w, height=h, angle=0, strokeColor='#1e1e1e',
             backgroundColor='transparent', fillStyle='solid', strokeWidth=1, strokeStyle='solid',
             roughness=0, opacity=100, groupIds=[], frameId=None, roundness=None,
             seed=random.randint(1, 2**31), version=1, versionNonce=random.randint(1, 2**31),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False)
    e.update(kw)
    return e


def main():
    tree = layout(collapse(json.load(open(sys.argv[1]))))
    elements, n = [], [0]

    def nid():
        n[0] += 1
        return f'e{n[0]}'

    def emit(node, parent_rect=None):
        _, color = style(node)
        rid, tid = nid(), nid()
        label, H = node['_label'], node['_h']
        rect = base('rectangle', rid, node['_x'], node['_y'], W, H, backgroundColor=color,
                    roundness={'type': 3}, boundElements=[{'type': 'text', 'id': tid}],
                    strokeStyle='dashed' if node['type'] == 'Note' else 'solid')
        text = base('text', tid, node['_x'] + 6, node['_y'] + 8, W - 12, H - 16, text=label,
                    originalText=label, fontSize=DESC_FONT, fontFamily=3, textAlign='center',
                    verticalAlign='middle', containerId=rid, lineHeight=1.25, baseline=10,
                    autoResize=True)
        elements.extend([rect, text])
        if parent_rect is not None:
            aid = nid()
            sx, sy = parent_rect['x'] + W, parent_rect['y'] + parent_rect['height'] / 2
            ex, ey = rect['x'], rect['y'] + H / 2
            elements.append(base('arrow', aid, sx, sy, ex - sx, ey - sy, points=[[0, 0], [ex - sx, ey - sy]],
                                 startBinding={'elementId': parent_rect['id'], 'focus': 0, 'gap': 1},
                                 endBinding={'elementId': rid, 'focus': 0, 'gap': 1},
                                 startArrowhead=None, endArrowhead='arrow', roundness={'type': 2},
                                 strokeColor='#868e96', lastCommittedPoint=None))
            parent_rect['boundElements'].append({'type': 'arrow', 'id': aid})
            rect['boundElements'].append({'type': 'arrow', 'id': aid})
        for c in node.get('children', []):
            emit(c, rect)

    emit(tree)
    # legend
    lx, ly, H, DY = -DX, 0, 44, 60
    for i, (label, color) in enumerate([('→ Sequence: all children in order', '#a5d8ff'),
                                        ('? Selector: first child that succeeds', '#ffd8a8'),
                                        ('⇉ Parallel: all children each tick', '#d0bfff'),
                                        ('◇ Decorator (Inverter)', '#dee2e6'),
                                        ('Condition (Is… / Has…)', '#b2f2bb'),
                                        ('Action', '#fff3bf')]):
        rid, tid = nid(), nid()
        elements.append(base('rectangle', rid, lx, ly + i * DY, W, H, backgroundColor=color,
                             roundness={'type': 3}, boundElements=[{'type': 'text', 'id': tid}]))
        elements.append(base('text', tid, lx + 6, ly + i * DY + 12, W - 12, 20, text=label, originalText=label,
                             fontSize=13, fontFamily=3, textAlign='center', verticalAlign='middle',
                             containerId=rid, lineHeight=1.25, baseline=12, autoResize=True))
    title = 'Booster default 3v3 AI — team behaviour tree (py_trees, ticked every control cycle)'
    elements.append(base('text', nid(), lx, ly - 70, 900, 30, text=title, originalText=title, fontSize=22,
                         fontFamily=3, textAlign='left', verticalAlign='top', containerId=None,
                         lineHeight=1.25, baseline=20, autoResize=True))
    doc = {'type': 'excalidraw', 'version': 2, 'source': 'https://excalidraw.com', 'elements': elements,
           'appState': {'viewBackgroundColor': '#ffffff', 'gridSize': None}, 'files': {}}
    json.dump(doc, open(sys.argv[2], 'w'), ensure_ascii=False)
    print(f'{sys.argv[2]}: {sum(e["type"] == "rectangle" for e in elements)} boxes')


if __name__ == '__main__':
    main()
