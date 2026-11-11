"""Body-only optical/servo calibration; no formal subject and no Core import."""
import argparse
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parents[2]),str(HERE.parents[2]/'src')]
import mujoco
import numpy as np

from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.eye_hand_world import teacher_eye_angle


def run():
    rows=[]
    for shape in range(4):
        for target in range(4):
            world=ActiveEyeClassroom(seed=91,weather_seed=47)
            xy=[[-.64,-.64],[.64,-.64],[-.64,.64],[.64,.64]][target]
            world.set_scene([(shape,0),(1,1),(2,2),(3,3)],
                            positions=[xy,*[[x,y] for x,y in [[-.55,-.55],[.55,-.55],[-.55,.55],[.55,.55]] if [x,y]!=[[-.55,-.55],[.55,-.55],[-.55,.55],[.55,.55]][target]]])
            angle=teacher_eye_angle(world,xy,z=.16)
            assert max(abs(angle))<world.eye_config.angle_limit_rad
            for _ in range(60):
                world.advance_physics(eye_action=world.eye_servo(angle))
            assert max(abs(world.project(xy)))<1e-6
            ob=world.observe()
            receptor=world.receptor_for_point(xy)
            ray=world.selected_ray(receptor,ob)
            endpoint=(world.origin+(.16-world.origin[2])/ray[2]*ray)[:2]
            error=float(np.linalg.norm(endpoint-xy))
            assert error<.15
            target_geom=mujoco.mj_name2id(world.model,mujoco.mjtObj.mjOBJ_GEOM,'o0')
            visible=[]
            for hand_at_target in (False,True):
                if hand_at_target:
                    world.pointer.x,world.pointer.y=xy
                world.observe()  # Update physical hand and marker geometry.
                hits=0
                for directions in world._subdirections:
                    for direction in directions:
                        geom=np.array([-1],dtype=np.int32)
                        mujoco.mj_ray(world.model,world.data,world.origin,direction,None,1,-1,geom)
                        hits+=int(geom[0]==target_geom)
                visible.append(hits)
            assert min(visible)>0, 'target fully occluded by own hand'
            rows.append({'shape': shape,'quadrant': target,'eye_angle': list(angle),
                             'ray_error_m': error,'target_subrays_before_point': visible[0],
                             'target_subrays_after_point': visible[1]})
    return {'kind': 'apparatus-calibration','core_created': False,'formal_subject_created': False,
                'cases': rows,'maximum_hand_ray_error_m': max(r['ray_error_m'] for r in rows),
                'note': 'Own hand remains visible and may partly occlude targets; no object-specific image crop or sensory change.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path)
    a=p.parse_args();result=run()
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
