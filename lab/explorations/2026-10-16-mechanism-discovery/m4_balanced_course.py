"""Bounded prospective course. Inference never receives task/target metadata.

No CLI or standalone launch: execution requires the registered driver, frozen
protocol, accepted instrument and verified whole-state/resource prerequisites.
"""
import copy
import itertools
import math
import time

import numpy as np

from m4_instrument import window
from lab.tools.eye_hand_world import teacher_eye_angle

MODES=('eye','hand','joint')
CUES=(('看','瞧'),('指','点'),('合','同'))
POSITIONS=((- .55,-.35),(.55,.35),(-.55,.15),(.55,-.15),(-.55,.35),(.55,-.35),(-.55,-.15),(.55,.15))
PERMUTATIONS=tuple(itertools.permutations(MODES))
TICKS=60
DT=.05


def task(identifier,mode,position,alias,*,material=0,shape=0):
    return {'id':identifier,'mode':mode,'xy':list(position),'cue':CUES[MODES.index(mode)][alias],
            'alias':alias,'item':[shape,material],'seconds':3.,'teacher_and_scorer_only_mode':True}


def bank(origin):
    if type(origin) is not int or not 0<=origin<8:raise ValueError('eight exploratory origins')
    def diagnostic(label,alias,shift=False):
        rows=[]
        for j in range(4):
            order=PERMUTATIONS[(origin+j)%6]
            for mode in order:
                k=MODES.index(mode);position_index=(j+k)%4;p=np.array(POSITIONS[2*position_index])
                if shift:p=p+np.array([-.03*np.sign(p[0]),.02*(-1)**position_index])
                rows.append(task(f'{label}-{len(rows):03d}',mode,p,alias,material=position_index,shape=(position_index+1)%4))
        return rows
    rounds=[]
    for cycle in range(2):
        blocks=[]
        for block in range(8):
            rows=[]
            for mode in PERMUTATIONS[(origin+block+cycle)%6]:
                k=MODES.index(mode);p=POSITIONS[(3*block+k)%8]
                rows.append(task(f't{cycle}-b{block}-{mode}',mode,p,(block+cycle)%2,
                                 material=(block+k+cycle)%4,shape=(block+2*k+cycle)%4))
            blocks.append(rows)
        rounds.append(blocks)
    return {'origin':origin,'warmup_seconds':3.,'pre':diagnostic('pre',0),
            'teaching_rounds':rounds,'development':diagnostic('development',0),
            'confirmation':diagnostic('confirmation',1,True),
            'calibration_updates_per_balanced_block':120,'total_motor_updates':1920,
            'source_sequence':'birth,warmup,pre,48 demonstrations with continuing calibration,development,confirmation',
            'ordinary_seconds':3+36+144+36+36}


def project(ob,xyz):
    c=ob['camera'];delta=np.asarray(xyz)-np.asarray(c['origin_m']);depth=float(delta@c['forward'])
    return np.array([delta@c['right'],delta@c['up']])/depth,depth


def receptor(ob,xyz):
    uv,_=project(ob,xyz)
    return int(np.argmin(np.sum((np.asarray(ob['retinal_centers'])-uv)**2,axis=1)))


def held_eye_point(world,angle):
    base=-world.origin/np.linalg.norm(world.origin);right=np.array([1.,0.,0.]);up=np.cross(right,base)
    yaw,pitch=angle;ray=math.cos(pitch)*(math.cos(yaw)*base+math.sin(yaw)*right)+math.sin(pitch)*up
    return world.origin+(.16-world.origin[2])/ray[2]*ray


def autonomous(a,rows):
    """Only raw activity and the existing truth-free geometric executor."""
    intent=a.motor.intent(window(a.motor.layout,rows))
    if rows:a.executor.accept(intent,rows[-1]['observation'],a.session.world)
    return intent


def score(t,rows,initial_eye,initial_hand):
    obs=[r['observation'] for r in rows];xy=np.asarray(t['xy'])
    inside=[project(o,[*xy,.16])[1]>0 and np.max(np.abs(project(o,[*xy,.16])[0]))<=o['eye_config']['center_half_width'] for o in obs]
    gaze=[v and np.linalg.norm(o['eye_velocity_rad_s'])<.08 for v,o in zip(inside,obs)]
    distances=[float(np.linalg.norm([o['pointer']['x']-xy[0],o['pointer']['y']-xy[1]])) for o in obs]
    pointing=[v<=.15 for v in distances]
    eye_hold=[np.linalg.norm(np.array(o['eye_angle_rad'])-initial_eye)<=.025 and np.linalg.norm(o['eye_velocity_rad_s'])<.08 for o in obs]
    hand_hold=[np.linalg.norm(np.array([o['pointer']['x'],o['pointer']['y']])-initial_hand)<=.05
               and np.hypot(o['pointer']['vx'],o['pointer']['vy'])<.01 for o in obs]
    eye_ok=all((eye_hold if t['mode']=='hand' else gaze)[-6:])
    hand_ok=all((hand_hold if t['mode']=='eye' else pointing)[-6:])
    decisions=[r['new_intent'] for r in rows if r['new_intent'] is not None]
    eye_cost=float(np.mean([min(4.,np.max(np.abs(project(o,[*xy,.16])[0]))/o['eye_config']['center_half_width']) for o in obs[-6:]]))
    hand_cost=float(np.mean([min(4.,d/.15) for d in distances[-6:]]))
    return {'id':t['id'],'mode':t['mode'],'eye_success':bool(eye_ok),'hand_success':bool(hand_ok),
            'joint_success':bool(eye_ok and hand_ok),'target_gaze_success':bool(all(gaze[-6:])),
            'target_point_success':bool(all(pointing[-6:])),'eye_initially_inside':bool(inside[0]),
            'hand_initially_arrived':bool(pointing[0]),'hand_final_error_m':distances[-1],
            'new_decisions':len(decisions),'move_decisions':sum(bool(x['move']) for x in decisions),
            'wait_decisions':sum(not x['move'] for x in decisions),'behavior_window_seconds':3.,
            'eye_target_cost':eye_cost,'hand_target_cost':hand_cost}


def trial(a,t,*,teaching=False,collect=False):
    s=a.session;w=s.world;start=s.engine.time_us
    w.set_scene([t['item']],positions=[t['xy']]);w.marker=None
    frames=list(s.sensor.frames(t['cue']))
    if len(frames)>10:raise ValueError('cue exceeds fixed 500ms acquisition')
    initial_eye=w.eye_angle.copy();initial_hand=np.array([w.pointer.x,w.pointer.y])
    hold_point=held_eye_point(w,initial_eye)
    desired_eye=initial_eye if t['mode']=='hand' else teacher_eye_angle(w,t['xy'],z=.16)
    desired_hand=initial_hand if t['mode']=='eye' else np.array(t['xy'])
    rows=[];values={k:[] for k in ('x','eye','hand','move')};samples=[];inference_ns=0;physical_ns=0
    for i in range(TICKS):
        intent=None
        if i>=10 and i%10==0:
            clock=time.perf_counter_ns();intent=autonomous(a,rows);inference_ns+=time.perf_counter_ns()-clock
        own_eye,own_hand=a.executor.commands(w)
        if teaching:
            eye=w.eye_servo(desired_eye)
            hand=np.clip(3*(desired_hand-[w.pointer.x,w.pointer.y])-.9*np.array([w.pointer.vx,w.pointer.vy]),-1,1)
        else:eye,hand=own_eye,own_hand
        clock=time.perf_counter_ns()
        row=s.tick(frames[i] if i<len(frames) else None,eye=eye,hand=hand)
        physical_ns+=time.perf_counter_ns()-clock
        row.update(new_intent=copy.deepcopy(intent),executor=a.executor.state(),assistance=teaching,
                   own_eye_action=own_eye.tolist(),own_hand_action=own_hand.tolist(),cue=t['cue'])
        rows.append(row);a.cursor+=1
        if (teaching or collect) and (i+1)%10==0:
            # Teacher targets and mode are never passed to autonomous().
            ob=row['observation'];move=int(t['mode']!='eye')
            values['x'].append(window(a.motor.layout,rows))
            values['eye'].append(receptor(ob,hold_point if t['mode']=='hand' else [*t['xy'],.16]))
            values['hand'].append(receptor(ob,[*t['xy'],.16]) if move else -1)
            values['move'].append(move)
            samples.append({'time_us':int(row['activity']['time_us']),'move':move,
                            'teacher_label_source':'declared task; not gaze-correctness gated'})
    result=score(t,rows,initial_eye,initial_hand)
    result.update(teaching=teaching,autonomous_success=None if teaching else result['joint_success'],
                  start_us=start,end_us=s.engine.time_us,inference_ns=inference_ns,sensor_core_body_ns=physical_ns)
    if s.engine.time_us!=start+3000000:raise RuntimeError('trial clock contract')
    return rows,values,result,samples
