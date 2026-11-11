"""No-Core physical controls for forced selection versus no decoder call.

This is an explicit external experiment, not a changed deployed control path.
Zero-valued input and no frame are different conditions. Wind remains present.
"""
import numpy as np
from experiment import (study,Case,OLD,WORK,ROOT,old,read_json,new_json,encoded,
                       DetailedClassroom,POSITIONS,Pointer)
from lab.tools.spatial_choice import SpatialChoice


def main():
    s=study();case=Case(s,'C-absent-activity')
    try:
        model,_=SpatialChoice.restore(OLD/'cases/r4-exposure-shared-fit/controller',old.device())
        state=old.read_gzip(OLD/'cases/r4-exposure/checkpoint.json.gz')
        tasks=read_json(ROOT/'lab/explorations/2026-10-06-vision-correction/confirmation-tasks.json')
        output=[]
        for condition in ('zero-valued-frame','no-frame-no-decoder-call'):
            for task in tasks:
                s.guard();w=DetailedClassroom.restore(state['world'])
                w.set_scene(task['items'],task['variant']);w.marker=None;w.pointer=Pointer(*task['start'])
                w.acceleration=[0.,0.];w.motor_power=0.
                # Same1s query period, with weather/body physics but no Core.
                for _ in range(20):w.advance_physics()
                start=[w.pointer.x,w.pointer.y]
                selected=int(model.predict(np.zeros((1,8,model.full_features),np.float32)).argmax(-1)[0]) if condition=='zero-valued-frame' else None
                trajectory=[];actions=[]
                for _ in range(40):
                    action=w.pointer.teacher_action(POSITIONS[selected]) if selected is not None else np.zeros(2)
                    actions.append(action.tolist());w.advance_physics(action)
                    trajectory.append([w.time_s,w.pointer.x,w.pointer.y,w.motor_power])
                output.append({'condition':condition,'task':task,'selected':selected,
                    'decoder_invocations':int(selected is not None),'nonzero_commands':sum(bool(np.any(np.asarray(a)!=0)) for a in actions),
                    'target_correct':None if selected is None else selected==task['slot'],
                    'distance_m':float(np.linalg.norm(np.array(trajectory[-1][1:3])-start)),
                    'actions':actions,'trajectory':trajectory})
        new_json(case.path/'trials.json',output)
        groups={condition:{'n':len(rows),'decoder_invocations':sum(r['decoder_invocations'] for r in rows),
                            'nonzero_commands':sum(r['nonzero_commands'] for r in rows),
                            'correct':sum(r['target_correct'] is True for r in rows),
                            'choices':sorted({r['selected'] for r in rows if r['selected'] is not None}),
                            'max_displacement_m':max(r['distance_m'] for r in rows)}
                for condition in ('zero-valued-frame','no-frame-no-decoder-call')
                for rows in [[r for r in output if r['condition']==condition]]}
        case.finish({'core_created':False,'groups':groups,
                     'meaning':'zero input to a forced-choice head still selects; missing frame here means no decoder call; passive drift remains',
                     'production_change':False})
    finally:s.db.close()


if __name__=='__main__':main()
