#!/usr/bin/env python3
"""Test-only foot kinematics from live physics, with no simulator commands."""
import argparse
import json
import logging
from pathlib import Path
import sys
import threading
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=2700)
    args=parser.parse_args()
    sys.path.insert(0,'/usr/local/booster_robot/booster_robocup_sim')
    logging.basicConfig(level=logging.ERROR)
    import mujoco
    import numpy as np
    from core.mujoco_model_cache import acquire_scene
    from core.physics_transport import PhysicsTransportConfig
    from transport.websocket.physics_ws import PhysicsWebSocketClient
    logging.getLogger().setLevel(logging.ERROR)
    latest={}
    lock=threading.Lock()
    client=PhysicsWebSocketClient(PhysicsTransportConfig(port=8788),owner='kick-foot-observer')
    def receive(key,value):
        with lock:
            latest[key]=(value,time.monotonic())
    client.subscribe_simulation_state(lambda v:receive('scene',v))
    client.subscribe_physics_state(lambda v:receive('physics',v))
    client.subscribe_game_control_world(lambda v:receive('world',v))
    client.connect()
    try:
        end=time.monotonic()+15
        while len(latest)<3 and time.monotonic()<end:
            time.sleep(.1)
        if len(latest)<3:
            raise RuntimeError('Missing physics or scene state')
        scene=latest['scene'][0]
        model=acquire_scene('/tmp/booster-runtime-scenes/'+scene.model_revision+'.mjspec.zip',owner='kick-foot-observer').model
        robot=next(r for r in latest['world'][0]['world']['robots'] if r['name']=='robot1')
        root=robot['bodyId']
        ball=latest['world'][0]['world']['ballBodyId']
        feet={}
        for i in range(model.nbody):
            name=model.body(i).name
            if model.body_rootid[i]==root and 'foot_link' in name:
                feet[name]=i
        if len(feet)!=2:
            raise RuntimeError('Expected two foot links: '+str(feet))
        data=mujoco.MjData(model)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('w',buffering=1) as stream:
            stream.write(json.dumps({'kind':'metadata','revision':scene.model_revision,'feet':feet,'root':root})+'\n')
            last_frame=None
            end=time.monotonic()+args.seconds
            while time.monotonic()<end:
                with lock:
                    state,receipt=latest['physics']
                    revision=latest['scene'][0].model_revision
                if revision!=scene.model_revision:
                    raise RuntimeError('Topology changed')
                if time.monotonic()-receipt>20:
                    raise RuntimeError('Physics stalled')
                if state.frame_id!=last_frame:
                    last_frame=state.frame_id
                    data.qpos[:]=state.qpos
                    mujoco.mj_kinematics(model,data)
                    rotation=data.xmat[root].reshape(3,3)
                    positions={name:{'world':data.xpos[i].tolist(),
                                     'relative':(rotation.T@(data.xpos[i]-data.xpos[root])).tolist()}
                               for name,i in feet.items()}
                    stream.write(json.dumps({'kind':'feet','wall_time':time.time(),'sim_time':state.time,
                                             'root':data.xpos[root].tolist(),'ball':data.xpos[ball].tolist(),
                                             'feet':positions})+'\n')
                time.sleep(.02)
    finally:
        client.disconnect()


if __name__=='__main__':
    main()
