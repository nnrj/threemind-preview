"""E61: free bodily exploration before identical teacher-led eye/hand lessons.

Every stage is bounded and append-only. Core dynamics and old trials are intact.
"""
import argparse
from collections import deque
from dataclasses import replace
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
from lab.tools.body_playground import BodyPlayground, ExploratoryMotor
from lab.tools.sensorimotor_session import SensorimotorSession, growth_summary
from lab.tools.continuous_motor import ContinuousMotor
from lab.tools.service_study import Study, StudyConfig, new_json, read_json, write_gzip, encoded
HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/body-exploration-20261007'
PREVIOUS = ROOT/'lab/explorations/2026-10-07-eye-hand-learning/experiment.py'
spec = importlib.util.spec_from_file_location('e60_teaching', PREVIOUS)
e60 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e60)
SOURCES = ((223, 47), (279, 103))
GROUPS = ('explore', 'quiet', 'yoked')
TAG = ''
ACTIVITY_GAIN = 1.


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force:
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (self.work/'cases').glob('*/stopped.json'))
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+getattr(self, 'failed_wall', 0)+active > self.settings.wall_seconds:
            raise RuntimeError('aggregate compute including failed attempts')


def study(prepare=False):
    # The only permitted database is the explicitly authorized local project DB.
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u = urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('localhost', '127.0.0.1') or u.port != 5433 or u.path != '/threemind':
        raise RuntimeError('E61 permits only localhost:5433/threemind')
    s = BoundedStudy(StudyConfig('body-exploration/1', 'E61 学前探索与学会身体', HERE, WORK, 4,
        instance_limit=320, wall_seconds=7200, storage_soft=6*2**30, storage_hard=8*2**30,
        usage_soft_delta=5, usage_hard_delta=8), prepare=prepare)
    amendment=WORK/'compute-budget-amendment.json'
    if amendment.exists():
        approved=read_json(amendment)
        if approved.get('original_wall_seconds')!=7200 or approved.get('effective_wall_seconds')!=10800:
            raise ValueError('unknown explicit compute-budget amendment')
        s.settings=replace(s.settings,wall_seconds=10800)
    extension=WORK/'continuation-budget-amendment.json'
    if extension.exists():
        approved=read_json(extension)
        if (approved.get('previous_wall_seconds'),approved.get('effective_wall_seconds'),
            approved.get('usage_soft_delta'),approved.get('usage_hard_delta')) != (10800,12600,8,10):
            raise ValueError('unknown explicit continuation amendment')
        s.settings=replace(s.settings,wall_seconds=12600,usage_soft_delta=8,usage_hard_delta=10)
    return s


def instance(s, **kwargs):
    path = WORK/'instances.json'; n = read_json(path)['created']
    if n >= s.settings.instance_limit: raise RuntimeError('instance creation/restore budget')
    path.write_bytes(encoded({'created': n+1})); return SensorimotorSession(**kwargs)


def run(s, key, execute):
    p = WORK/'cases'/key
    if (p/'result.json').exists(): return read_json(p/'result.json')
    if p.exists(): raise RuntimeError('preserve incomplete case; register another key: '+key)
    s.guard(True); p.mkdir(parents=True); start = time.monotonic()
    sources = [ROOT/'lab/tools'/n for n in ('body_playground.py', 'continuous_motor.py', 'eye_hand_world.py',
        'active_eye.py', 'sensorimotor_session.py')] + [PREVIOUS]
    versions = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}
    digest = hashlib.sha256(encoded(versions)).hexdigest(); revision = WORK/'tool-revisions'/digest
    if not revision.exists():
        revision.mkdir(parents=True)
        for f in sources:
            dest = revision/f.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dest)
        new_json(revision/'manifest.json', versions)
    s.active_case = SimpleNamespace(born_wall=start)
    new_json(p/'started.json', {'epoch': time.time(), 'runner_signature': s.runner_signature, 'tools': digest})
    try:
        result = execute(p) | {'wall_seconds': time.monotonic()-start, 'runner_signature': s.runner_signature, 'tools': digest}
        new_json(p/'result.json', result)
        s.active_case = None; s.completed_count += 1; s.completed_wall += result['wall_seconds']
        print(json.dumps({'case': key, **result}, ensure_ascii=False), flush=True)
        return result
    except Exception as error:
        new_json(p/'stopped.json', {'error': str(error), 'wall_seconds': time.monotonic()-start}); raise


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            for row in json.loads(line)['process']: yield row


def explore(s, source, group, seconds=180.):
    key = f'A-{TAG}{source}-{group}' if seconds == 180 else f'pilot-{TAG}{source}-{group}-{seconds:g}'
    def execute(p):
        seed, weather = SOURCES[source]
        c = instance(s, world=BodyPlayground(weather_seed=weather), seed=seed, plasticity=group != 'yoked')
        motor = ExploratoryMotor(c.layout.width, seed=seed, activity_gain=ACTIVITY_GAIN)
        write_gzip(p/'initial.json.gz', c.snapshot()); new_json(p/'motor-initial.json', motor.state())
        tape = iter(rows(WORK/'cases'/f'A-{TAG}{source}-explore'/'process.jsonl.gz')) if group == 'yoked' else None
        trace = []; eye=[]; hand=[]; commands=[]; core_commands=[]; matches=0; maxdiff=0.; sounds=0.; moves=0.
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as out:
            for i in range(round(seconds/.05)):
                reference = next(tape) if tape is not None else None
                parts = None
                if reference:
                    cmd = np.array(reference['eye_action']+reference['hand_action']+reference['mouth_action'])
                elif group == 'quiet': cmd = np.zeros(6)
                else:
                    raw = c.layout.frame(c.current) if c.current else np.zeros(c.layout.width)
                    cmd, parts = motor.action(raw)
                row = c.tick(eye=cmd[:2], hand=cmd[2:4], mouth=cmd[4:], guard=s.guard)
                row['action_source'] = {'explore':'自由探索：匿名活动接线＋单列运动波动',
                    'quiet':'等时静置：零命令，感觉与可塑性继续', 'yoked':'研究重放：同动作，探索期结构学习关闭'}[group]
                if parts: row['developmental_motor'] = parts; core_commands.append(parts['core_component'])
                if reference:
                    # Small per-frame value comparison, not a repeated file hash.
                    diff = float(np.max(np.abs(np.asarray(row['observation']['values'])-reference['observation']['values'])))
                    maxdiff=max(maxdiff,diff); matches+=int(diff==0 and row['stimulus']['channels']==reference['stimulus']['channels'])
                ob=row['observation']; eye.append(ob['eye_angle_rad']); hand.append([ob['pointer']['x'],ob['pointer']['y']])
                commands.append(cmd); sounds += float(sum(ob['toy_resonance_J'])>1e-7)
                moves=max(moves,float(np.max(np.linalg.norm(np.array(ob['positions'])-np.array(ob['toy_anchors_m']),axis=1))))
                trace.append(row)
                if len(trace)==60 or i==round(seconds/.05)-1:
                    out.write(encoded({'kind':'exploration','condition':group,'process':trace}).decode()+'\n'); trace=[]
                if i%600==599: print(json.dumps({'stage':key,'sim_s':c.world.time_s,'contacts':c.world.contact_count}),flush=True)
        if tape is not None:
            if next(tape,None) is not None: raise RuntimeError('unconsumed yoked tape')
            if matches != round(seconds/.05): raise RuntimeError('yoked physical inputs diverged')
        if group=='yoked': c.engine.reconfigure(replace(c.engine.config,plasticity=True))
        write_gzip(p/'checkpoint.json.gz',c.snapshot()); new_json(p/'motor-final.json',motor.state())
        eye=np.array(eye);hand=np.array(hand);commands=np.array(commands)
        return {'source':source,'group':group,'seconds':seconds,'activity_gain':ACTIVITY_GAIN,'contacts':c.world.contact_count,
            'eye_range':np.ptp(eye,axis=0).tolist(),'hand_range':np.ptp(hand,axis=0).tolist(),
            'eye_path_rad':float(np.linalg.norm(np.diff(eye,axis=0),axis=1).sum()),
            'hand_path_m':float(np.linalg.norm(np.diff(hand,axis=0),axis=1).sum()),
            'eye_boundary_fraction':float(np.mean(np.max(np.abs(eye),axis=1)>.97*c.world.eye_config.angle_limit_rad)),
            'toy_sound_seconds':sounds*.05,'max_toy_displacement_m':moves,
            'command_saturated_fraction':float(np.mean(np.abs(commands)>.95)),
            'core_command_saturated_fraction':float(np.mean(np.abs(core_commands)>.95)) if core_commands else None,
            'identical_input_frames':matches if group=='yoked' else None,'max_input_difference':maxdiff,
            **growth_summary(c.snapshot())}
    return run(s,key,execute)


def classroom(c):
    """Explicitly reset external apparatus only, keeping Core and its clock."""
    w=BodyPlayground(weather_seed=c.world.weather_seed,toys=False)
    w.time_s=c.engine.time_us/1e6
    if w.channels != c.world.channels: raise RuntimeError('sensory identity changed')
    c.world=w


def curriculum():
    schedule=[]; onset=0.
    for mode in e60.MODES:
        for repeat in range(10):
            schedule.append({'mode':mode,'repeat':repeat,'onset_s':onset});onset+=3
    for repeat,gap in enumerate((6.,12.,24.),10):
        onset+=gap
        for mode in e60.MODES:
            schedule.append({'mode':mode,'repeat':repeat,'onset_s':onset});onset+=3
    return schedule


def teach(s,source,group):
    key=f'B-{TAG}{source}-{group}'
    def execute(p):
        c=instance(s,state=e60.read_gzip(WORK/'cases'/f'A-{TAG}{source}-{group}'/'checkpoint.json.gz'))
        classroom(c);start=c.world.time_s; data=[];schedule=[]
        write_gzip(p/'initial.json.gz',c.snapshot());new_json(p/'layout.json',c.layout.channels)
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i,item in enumerate(curriculum()):
                gap=[]
                while c.world.time_s-start+1e-6<item['onset_s']:
                    c.world.marker=None;row=c.tick(guard=s.guard);row['action_source']='复习间隔：环境及身体反馈持续';gap.append(row)
                if gap:out.write(encoded({'kind':'interval','process':gap}).decode()+'\n')
                spec=e60.task(i,mode=item['mode'])|item
                record,samples=e60.lesson(s,c,spec);data.extend(samples)
                out.write(encoded(record).decode()+'\n');schedule.append(item|{'actual_onset_s':record['process'][0]['observation']['time_s']})
                if i%10==0:print(json.dumps({'stage':key,'lesson':i+1,'of':52}),flush=True)
        e60.pack_features(data,p/'features.npz');write_gzip(p/'checkpoint.json.gz',c.snapshot());new_json(p/'schedule.json',schedule)
        return {'source':source,'group':group,'lessons':52,'samples':len(data),**growth_summary(c.snapshot())}
    return run(s,key,execute)


def validation(s,source,group):
    key=f'V-{TAG}{source}-{group}'
    def execute(p):
        c=instance(s,state=e60.read_gzip(WORK/'cases'/f'B-{TAG}{source}-{group}'/'checkpoint.json.gz'));classroom(c);data=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i in range(12):
                rec, samples=e60.lesson(s,c,e60.task(i,'validation',e60.MODES[i%4]));data.extend(samples)
                out.write(encoded(rec).decode()+'\n')
        e60.pack_features(data,p/'features.npz')
        return {'source':source,'group':group,'samples':len(data),'demonstrations':12}
    return run(s,key,execute)


def fit(s,source,group):
    def execute(p):
        folder=WORK/'cases'/f'B-{TAG}{source}-{group}'
        data=np.load(folder/'features.npz');val=np.load(WORK/'cases'/f'V-{TAG}{source}-{group}'/'features.npz')
        head=ContinuousMotor(read_json(folder/'layout.json'),organization='shared',seed=223,readout_version=2).to(e60.device())
        fitted=head.fit(data['activity'],data['y'],validation=(val['activity'],val['y']),steps=1600,check=s.guard)
        head.save(p/'controller',input_source='activity')
        return {'source':source,'group':group,'fit':fitted}
    return run(s,f'C-{TAG}{source}-{group}',execute)


def phase_metrics(rec):
    r=rec['result'];rows=rec['process'];eye=np.array([x['observation']['eye_angle_rad'] for x in rows])
    hand=np.array([[x['observation']['pointer'][k] for k in ('x','y')] for x in rows])
    ee=np.linalg.norm(eye-np.array(rec['scoring_only_eye_targets']),axis=1)
    he=np.linalg.norm(hand-np.array(rec['scoring_only_hand_targets']),axis=1)
    phases=[]
    for a,b in ((0,len(rows)//2),(len(rows)//2,len(rows))):
        phases.append({'eye_started_aligned':bool(ee[a]<=.075),'eye_entered':bool(ee[a]>.075 and np.any(ee[a:b]<=.075)),
            'eye_ended_aligned':bool(ee[b-1]<=.075),'hand_started_arrived':bool(he[a]<=.20),
            'hand_entered':bool(he[a]>.20 and np.any(he[a:b]<=.20)), 'hand_ended_arrived':bool(he[b-1]<=.20)})
    r['phases']=phases;return r


def evaluate(s,source,group,mode='normal',model_group=None,count=12):
    model_group=model_group or group;key=f'D-{TAG}{source}-{group}-read-{model_group}-{mode}'
    def execute(p):
        saved=e60.read_gzip(WORK/'cases'/f'B-{TAG}{source}-{group}'/'checkpoint.json.gz')
        head=ContinuousMotor.restore(WORK/'cases'/f'C-{TAG}{source}-{model_group}'/'controller',e60.device());results=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i in range(count):
                c=instance(s,state=saved);classroom(c)
                if mode in ('silence','rescue'):
                    pairs=[(e['source'],e['target']) for e in saved['core']['edges']]
                    c.engine.intervene(edges=pairs,action='silence')
                    if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
                rec,_=e60.lesson(s,c,e60.task(i,'test',e60.MODES[i%4]),assist=False,head=head,seconds=6.,retarget=True,intervention=mode)
                results.append(phase_metrics(rec));out.write(encoded(rec).decode()+'\n')
                if i==0:write_gzip(p/'first-end-state.json.gz',c.snapshot())
                if i%4==0:print(json.dumps({'stage':key,'trial':i+1,'of':count}),flush=True)
        new_json(p/'trials.json',results)
        eye=[p for r in results if r['mode'] in ('look','both') for p in r['phases']]
        hand=[p for r in results if r['mode'] in ('point','both') for p in r['phases']]
        return {'source':source,'group':group,'model_group':model_group,'mode':mode,'n':count,**e60.summarize(results),
            'eye_requested_phases':len(eye),'eye_enter_and_finish':sum(x['eye_entered'] and x['eye_ended_aligned'] for x in eye),
            'hand_requested_phases':len(hand),'hand_enter_and_finish':sum(x['hand_entered'] and x['hand_ended_arrived'] for x in hand)}
    return run(s,key,execute)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','pilot','explore','teach','validation','fit','evaluate','source-batch'])
    parser.add_argument('--source',type=int,choices=[0,1],default=0);parser.add_argument('--group',choices=GROUPS,default='explore')
    parser.add_argument('--model-group',choices=GROUPS);parser.add_argument('--mode',choices=['normal','silence','rescue','empty'],default='normal')
    parser.add_argument('--usage',type=int,default=5);parser.add_argument('--development',choices=['original','gain01'],default='original');args=parser.parse_args()
    global TAG, ACTIVITY_GAIN
    if args.development=='gain01':TAG='gain01-';ACTIVITY_GAIN=.1
    if args.stage=='prepare':
        WORK.mkdir(parents=True,exist_ok=True)
        if not (WORK/'usage.json').exists():new_json(WORK/'usage.json',{'used_percent':args.usage})
        if not (WORK/'instances.json').exists():new_json(WORK/'instances.json',{'created':0})
    s=study(args.stage=='prepare')
    try:
        if args.stage=='prepare':print(json.dumps({'project_id':s.project,'work':str(WORK)}))
        elif args.stage=='pilot':explore(s,args.source,'explore',20.)
        elif args.stage=='explore':explore(s,args.source,args.group)
        elif args.stage=='teach':teach(s,args.source,args.group)
        elif args.stage=='validation':validation(s,args.source,args.group)
        elif args.stage=='fit':fit(s,args.source,args.group)
        elif args.stage=='evaluate':evaluate(s,args.source,args.group,args.mode,args.model_group)
        elif args.stage=='source-batch':
            for group in GROUPS:
                explore(s,args.source,group);teach(s,args.source,group);validation(s,args.source,group);fit(s,args.source,group)
                evaluate(s,args.source,group)
    finally:s.db.close()


if __name__=='__main__':main()
