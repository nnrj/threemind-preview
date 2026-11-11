"""Recorded teaching intervals and optical occlusion; no Core execution.

Use the midpoint of every lesson, fixed before inspecting the measurements.
Geometry IDs are offline measurement labels, never sensory input channels.
"""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import mujoco
from lab.tools.active_eye import ActiveEyeClassroom,EyeConfig
from lab.tools.shape_color_world import Pointer
from lab.tools.service_study import new_json
WORK=ROOT/'.work/active-vision-20261007'


def count_rays(w,target):
    w._refresh_directions();w.model.geom_pos[w.self_id]=[w.pointer.x,w.pointer.y,.4]
    w.model.geom_pos[w.teacher_id]=[*w.marker,.52] if w.marker is not None else [0,0,-10]
    mujoco.mj_forward(w.model,w.data);geo=np.array([-1],dtype=np.int32);counts=[]
    for rays in w._subdirections:
        hits=0
        for ray in rays:
            mujoco.mj_ray(w.model,w.data,w.origin,ray,None,1,-1,geo);hits+=int(geo[0])==target
        counts.append(hits)
    return counts


def main():
    moments={i:[] for i in range(8)};optics=[];w=ActiveEyeClassroom()
    with gzip.open(WORK/'cases/B-teach-scan/process.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            record=json.loads(line)
            if record.get('kind')!='lesson':continue
            moments[record['item']].append(record['process'][0]['observation']['time_s'])
            ob=record['process'][len(record['process'])//2]['observation']
            w.set_scene(ob['items'],positions=ob['positions']);w.pointer=Pointer(**ob['pointer']);w.marker=ob['teacher_marker']
            w.eye_angle=np.array(ob['eye_angle_rad']);slot=int(np.argmin(np.linalg.norm(np.array(ob['positions'])-w.marker,axis=1)))
            target=mujoco.mj_name2id(w.model,mujoco.mjtObj.mjOBJ_GEOM,'o'+str(slot))
            shown=count_rays(w,target);w.marker=None;clear=count_rays(w,target)
            optics.append({'item':record['item'],'repeat':record['repeat'],'sample_time':ob['time_s'],
                           'target_subrays_with_teacher':sum(shown),'without_teacher':sum(clear),
                           'central_with_teacher':sum(shown[:36]),'central_without_teacher':sum(clear[:36])})
    spacing={str(i):{'starts':t,'start_intervals_s':np.diff(t).tolist()} for i,t in moments.items()}
    clear=sum(x['without_teacher'] for x in optics);shown=sum(x['target_subrays_with_teacher'] for x in optics)
    result={'spacing':spacing,'optical_midpoints':optics,'summary':{'lessons':len(optics),
        'target_subrays_with_teacher':shown,'without_teacher':clear,'occluded_fraction':1-shown/max(1,clear),
        'lesson_midpoints_target_completely_occluded':sum(x['without_teacher']>0 and not x['target_subrays_with_teacher'] for x in optics),
        'lesson_midpoints_target_sampled':sum(x['target_subrays_with_teacher']>0 for x in optics),
        'scope':'one fixed midpoint per recorded scan lesson; measured visibility, not comprehension'}}
    new_json(WORK/'teaching-audit.json',result);print(json.dumps(result['summary']))


if __name__=='__main__':main()
