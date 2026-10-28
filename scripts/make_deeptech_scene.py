#!/usr/bin/env python3
"""Build our local practice scene: Booster's K1 soccer field with robot1 in the DeepTech navy
shirt (chest armour) and robot2 as a blue team-2 opponent.

Writes <Booster Studio library>/scenes/deeptech_pitch_K1.bscene, a copy of the built-in
football_pitch_K1.bscene with only the manifest's robot list changed. The simulator paints a
robot's chest from its scene "color" when the scene loads (core/model_colors.py); robots added
live with attach_robot do not get painted. Booster's simulator and referee code are untouched.
"""
import json
import pathlib
import zipfile

LIB = pathlib.Path.home() / '.config/Booster Studio/simulator-library/scenes'
SRC, KEY = LIB / 'football_pitch_K1.bscene', 'deeptech_pitch_K1'
NAVY = [0x13 / 255, 0x15 / 255, 0x31 / 255, 1.0]  # sampled from the DeepTech team shirt
OPPONENT_BLUE = [0.1, 0.25, 0.85, 1.0]

src = zipfile.ZipFile(SRC)
manifest = json.loads(src.read('manifest.json'))
robot1 = dict(manifest['robot_instances'][0], team=1, color=NAVY)
# Spawn points must be OFF the field: the referee parks a penalized robot by resetting it
# to its spawn, so an in-field spawn leaves it on the pitch (endless reentry penalties).
# robot2 mirrors robot1, outside the other sideline, facing into the field.
robot2 = dict(robot1, name='robot2', root_body='robot2_Trunk', pos=[5.0, -5.0, 0.0],
              quat=[0.7073882691671998, 0.0, 0.0, 0.706825181105366], team=2, color=OPPONENT_BLUE)
manifest.update(id=KEY, name='DeepTech Soccer Field', origin='user', deletable=True,
                description='K1 soccer field: robot1 DeepTech navy vs robot2 opponent',
                robot_instances=[robot1, robot2], display_order=11)
for field in ('builtin_id', 'builtin_revision'):
    manifest.pop(field, None)

out = LIB / f'{KEY}.bscene'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as dst:
    for item in src.infolist():
        data = json.dumps(manifest, indent=2).encode() if item.filename == 'manifest.json' else src.read(item)
        dst.writestr(item, data)
print(out)
