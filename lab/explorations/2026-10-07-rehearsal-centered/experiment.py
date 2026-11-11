"""E63 bounded rehearsal comparison, preserving each complete organism."""
import argparse
import gzip
import importlib.util
import json
import hashlib
import shutil
from pathlib import Path
import sys
import time
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import Study, StudyConfig, read_json, new_json, encoded
from lab.tools.developmental_session import DevelopmentalSession
from lab.tools.developmental_motor import DevelopmentalMotor
from lab.tools.developmental_inspect import retained_calibration

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/rehearsal-centered-20261007'
OLD = ROOT/'.work/continuous-development-20261007/cases/s223-direct-aligned/system'
old_folder = ROOT/'lab/explorations/2026-10-07-continuous-development'
sys.path.insert(0, str(old_folder))
spec = importlib.util.spec_from_file_location('e62_registered', old_folder/'experiment.py')
E62 = importlib.util.module_from_spec(spec); spec.loader.exec_module(E62)


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force or not hasattr(self, 'failed_wall'):
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                                   if not (p.parent/'result.json').exists())
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+self.failed_wall+active > self.settings.wall_seconds:
            raise RuntimeError('total computation budget including failures')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u = urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port != 5433 or u.path != '/threemind':
        raise ValueError('authorized local research DB only')
    return BoundedStudy(StudyConfig('rehearsal-centered/1', 'E63 纠错复习与中央单物体认识', HERE, WORK, 18,
        instance_limit=64, wall_seconds=7200, storage_soft=int(1.8*2**30), storage_hard=4*2**30,
        usage_soft_delta=4, usage_hard_delta=6), prepare=prepare)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6); return 'cuda'
    return 'cpu'


def count_instance():
    p = WORK/'instances.json'; n = read_json(p)['created']
    if n >= 64: raise RuntimeError('instance budget')
    p.write_bytes(encoded({'created':n+1}))


def restore(path, **kwargs):
    count_instance(); return DevelopmentalSession.restore(path, device=device(), **kwargs)


def run(s, key, operation):
    p = WORK/'cases'/key
    if (p/'result.json').exists(): return read_json(p/'result.json')
    if p.exists(): raise RuntimeError('preserve partial case; declare recovery separately')
    s.allow_extension(); p.mkdir(parents=True); start = time.monotonic()
    paths=list((ROOT/'lab/tools').glob('developmental_*.py'))+[ROOT/'lab/tools'/n for n in
        ('rehearsal_memory.py','centered_recognition.py','sensorimotor_session.py','active_eye.py','body_playground.py')]
    manifest={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in paths if f.exists()}
    signature=hashlib.sha256(encoded(manifest)).hexdigest();dest=WORK/'tool-revisions'/signature
    if not dest.exists():
        for f in paths:
            if f.exists():
                target=dest/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        new_json(dest/'manifest.json',manifest)
    new_json(p/'started.json', {'epoch':time.time(), 'runner':s.runner_signature,'tools':signature})
    s.active_case = SimpleNamespace(born_wall=start)
    try:
        value = operation(p) | {'wall_seconds':time.monotonic()-start, 'runner':s.runner_signature}
        new_json(p/'result.json', value); s.active_case=None
        s.completed_count += 1; s.completed_wall += value['wall_seconds']
        print(encoded({'case':key, **value}).decode(), flush=True); return value
    except Exception as e:
        new_json(p/'stopped.json', {'error':str(e), 'wall_seconds':time.monotonic()-start}); raise


def teach(s, policy):
    def operation(p):
        a = restore(OLD, branch='e63-'+policy); a.phase='equal-refresher'
        policy_start = a.motor.configure_rehearsal(policy)
        initial_steps = a.motor.steps
        old = DevelopmentalMotor.restore(OLD/'motor')
        old.identity = a.motor.identity  # same original individual, explicit experimental sibling
        initial = retained_calibration(a.motor, old)
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as f:
            for i, k in enumerate(np.random.default_rng(62497).permutation(12)):
                for rep, assistance in enumerate((.7,.4,.1)):
                    rows, result = E62.lesson(s, a, E62.MODES[k//4], int(k%4), assistance=assistance, learning=True, corrective=True)
                    E62.record(f, a.phase, i*3+rep, rows, trial=result)
                E62.record(f, 'review-gap', i, E62.wait(s,a,2.))
                if i in (3,7): a.save(p/f'checkpoint-{i+1}')
                f.flush(); print(json.dumps({'stage':policy,'target':i+1,'steps':a.motor.steps}),flush=True)
        calibration = {'before_old':initial,'after_old':retained_calibration(a.motor,old),'after_new':retained_calibration(a.motor)}
        new_json(p/'calibration.json', calibration); a.save(p/'system')
        return {'policy':policy,'identity':a.identity,'steps_before':initial_steps,'steps_after':a.motor.steps,
                'updates':a.motor.steps-initial_steps,'policy_start':policy_start,'calibration':calibration,
                'sim_seconds':a.session.engine.time_us/1e6,'snapshot':str(p/'system')}
    return run(s, 'rehearsal-'+policy, operation)


def evaluate(s, policy, mode='normal'):
    def operation(p):
        a=restore(WORK/f'cases/rehearsal-{policy}/system',branch='test-'+mode); a.phase='evaluation'
        edges=[(e['source'],e['target']) for e in a.session.engine.capture_state().to_dict()['edges']]
        if mode in ('silence','rescue'):
            a.session.engine.intervene(edges=edges,action='silence')
            if mode=='rescue': a.session.engine.intervene(edges=edges,action='unsilence')
        before=a.motor.steps; scores=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,k in enumerate(np.random.default_rng(62411).permutation(12)):
                rows,result=E62.lesson(s,a,E62.MODES[k//4],int(k%4),seconds=4.)
                scores.append(result); E62.record(f,a.phase,i,rows,trial=result)
                print(json.dumps({'test':policy,'mode':mode,'trial':i,'reached':result['reached_from_outside']}),flush=True)
        assert a.motor.steps==before
        new_json(p/'scores.json',scores); a.save(p/'system')
        return {'policy':policy,'mode':mode,'n':len(scores),'end_reached':sum(r['end_reached'] for r in scores),
                'new_arrivals':sum(r['reached_from_outside'] for r in scores),'motor_steps':before,
                'mean_eye_error_rad':float(np.mean([r['eye_end_error_rad'] for r in scores if r['mode']!='point'])),
                'mean_hand_error_m':float(np.mean([r['hand_end_error_m'] for r in scores if r['mode']!='look']))}
    return run(s,f'motor-{policy}-{mode}',operation)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','rehearsal','evaluate'))
    p.add_argument('--policy',choices=('recent','reservoir','representative'),default='recent')
    p.add_argument('--mode',choices=('normal','silence','rescue'),default='normal')
    args=p.parse_args();s=study(args.command=='prepare')
    try:
        if args.command=='prepare':
            new_json(WORK/'usage.json',{'used_percent':18});new_json(WORK/'instances.json',{'created':0})
            s.guard(True);print(json.dumps({'project':s.project}))
        elif args.command=='rehearsal':teach(s,args.policy)
        else:evaluate(s,args.policy,args.mode)
    finally:s.db.close()


if __name__=='__main__':main()
