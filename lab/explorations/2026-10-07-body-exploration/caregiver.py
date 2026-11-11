"""Separately registered caregiver and matched withdrawal probes; no Core edits."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('e61',HERE/'experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
e.TAG='gain01-';e.ACTIVITY_GAIN=.1
from lab.tools.body_playground import BodyPlayground,ExploratoryMotor
from lab.tools.eye_hand_world import teacher_eye_angle
from lab.tools.service_study import write_gzip,new_json,encoded
from lab.tools.sensorimotor_session import growth_summary


def physical_metrics(rows):
    looking=[];stable=[];near=[]
    for r in rows:
        ob=r['observation']; eye=np.array(ob['eye_angle_rad'])
        # Reconstruct only the fixed camera geometry, not the simulated world.
        from types import SimpleNamespace
        world=SimpleNamespace(origin=np.array(ob['camera']['origin_m']))
        angles=[teacher_eye_angle(world,xy) for xy in ob['positions']]
        hit=bool(min(np.linalg.norm(eye-a) for a in angles)<=.075)
        looking.append(hit);stable.append(hit and np.linalg.norm(ob['eye_velocity_rad_s'])<.08)
        hand=np.array([ob['pointer']['x'],ob['pointer']['y']]);near.append(min(np.linalg.norm(hand-xy) for xy in np.array(ob['positions']))<=.2)
    return {'frames':len(rows),'looking_fraction':float(np.mean(looking)),
        'low_speed_looking_fraction':float(np.mean(stable)),'hand_near_toy_fraction':float(np.mean(near)),
        'new_contacts':rows[-1]['observation']['toy_contacts']-rows[0]['observation']['toy_contacts']}


def guided(s,source):
    key=f'A-gain01-{source}-guided'
    def execute(p):
        seed,weather=e.SOURCES[source]
        c=e.instance(s,world=BodyPlayground(weather_seed=weather),seed=seed)
        motor=ExploratoryMotor(c.layout.width,seed=seed,activity_gain=.1)
        write_gzip(p/'initial.json.gz',c.snapshot());new_json(p/'motor-initial.json',motor.state())
        phrases=('看看这个。','它在动。','听，响了。','来玩吧。'); frames=[];segments=[[],[]];buffer=[];speech=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i in range(3600):
                t=i*.05;enabled=t<120;slot=int(t//6)%4;phase=t%6
                c.world.external_forces[:]=0;c.world.external_sound[:]=0
                if enabled:
                    target=c.world.anchors[slot]+[.16*np.sin(2*np.pi*phase/3),.10*np.sin(2*np.pi*phase/4)]
                    c.world.external_forces[slot]=np.clip(5*(target-c.world.positions[slot])-.7*c.world.toy_velocity[slot],-1,1)
                    if i%120==0:
                        phrase=phrases[slot];frames=list(c.sensor.frames(phrase));speech.append({'time_s':t,'text':phrase})
                    if phase<1:c.world.external_sound[:]=[.008,.015,.011,.004]
                else:frames=[]
                text=frames.pop(0) if frames else None
                command,parts=motor.action(c.layout.frame(c.current) if c.current else np.zeros(c.layout.width))
                row=c.tick(text,eye=command[:2],hand=command[2:4],mouth=command[4:],guard=s.guard)
                row['developmental_motor']=parts;row['caregiver_present']=enabled
                row['action_source']='婴儿活动接线＋无目标运动波动；'+('母亲只移动玩具、发声和说话' if enabled else '母亲已停止引导')
                buffer.append(row);segments[0 if enabled else 1].append(row)
                if len(buffer)==60:
                    out.write(encoded({'kind':'exploration','condition':'guided' if enabled else 'withdrawn','process':buffer}).decode()+'\n');buffer=[]
                if i%600==599:print(json.dumps({'stage':key,'sim_s':c.world.time_s,'contacts':c.world.contact_count}),flush=True)
        write_gzip(p/'checkpoint.json.gz',c.snapshot());new_json(p/'motor-final.json',motor.state());new_json(p/'speech.json',speech)
        return {'source':source,'group':'guided','contacts':c.world.contact_count,
            'guided':physical_metrics(segments[0]),'withdrawn':physical_metrics(segments[1]),**growth_summary(c.snapshot())}
    return e.run(s,key,execute)


def probe(s,source,group,cut=False,preserve_wiring=False):
    key=('W2-' if preserve_wiring else 'W-')+f'gain01-{source}-{group}-'+('cut' if cut else 'normal')
    def execute(p):
        c=e.instance(s,state=e.e60.read_gzip(e.WORK/'cases'/f'A-gain01-{source}-{group}'/'checkpoint.json.gz'))
        w=BodyPlayground(weather_seed=e.SOURCES[source][1]);w.time_s=c.engine.time_us/1e6;c.world=w
        motor=ExploratoryMotor(c.layout.width,seed=e.SOURCES[source][0] if preserve_wiring else 801+source,activity_gain=.1);records=[]
        if preserve_wiring:
            original=e.read_json(e.WORK/'cases'/f'A-gain01-{source}-{group}'/'motor-initial.json')
            if not np.array_equal(motor.weights,np.array(original['weights'])):raise ValueError('preschool wiring must remain identical')
            # Match only the fresh motor-variation sequence, without replacing
            # the body's learned activity-to-actuator wiring.
            motor.rng=np.random.default_rng(801+source)
        new_json(p/'motor-initial.json',motor.state())
        write_gzip(p/'initial.json.gz',c.snapshot())
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i in range(600):
                raw=c.layout.frame(c.current) if c.current and not cut else np.zeros(c.layout.width)
                cmd,parts=motor.action(raw);row=c.tick(eye=cmd[:2],hand=cmd[2:4],mouth=cmd[4:],guard=s.guard)
                row['developmental_motor']=parts;row['action_source']='共同环境撤去引导：'+('切断Core到动作，只保留相同运动波动' if cut else '固定外设读取Core，叠加相同运动波动')
                records.append(row)
                if i%60==59:out.write(encoded({'kind':'exploration','process':records[-60:]}).decode()+'\n')
        write_gzip(p/'checkpoint.json.gz',c.snapshot())
        return {'source':source,'group':group,'cut':cut,'preschool_wiring_preserved':preserve_wiring,**physical_metrics(records),**growth_summary(c.snapshot())}
    return e.run(s,key,execute)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['register','guided','probe','teach'])
    parser.add_argument('--source',type=int,choices=[0,1],default=0);parser.add_argument('--group',choices=['explore','quiet','guided'],default='guided');parser.add_argument('--cut',action='store_true');parser.add_argument('--preserve-wiring',action='store_true')
    args=parser.parse_args();s=e.study()
    try:
        if args.stage=='register':s.note('caregiver-amendment','E61 母亲引导独立对照', (HERE/'caregiver-amendment.md').read_text(encoding='utf-8'))
        elif args.stage=='guided':guided(s,args.source)
        elif args.stage=='probe':probe(s,args.source,args.group,args.cut,args.preserve_wiring)
        elif args.stage=='teach':e.teach(s,args.source,'guided');e.validation(s,args.source,'guided');e.fit(s,args.source,'guided');e.evaluate(s,args.source,'guided')
    finally:s.db.close()


if __name__=='__main__':main()
