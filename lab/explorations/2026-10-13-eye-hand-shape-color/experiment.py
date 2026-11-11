"""E69 formal single-subject classroom; only the latest whole state can resume."""
import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '2'
import numpy as np
import torch
from classroom import interval, trial
from curriculum import STAGES, banks, correction, correction_calibration, initial
from journal import RESOURCE, BoundaryJournal, ResearchStudy, encoded, fixed_json, put, read, sha
from system import EyeHandSystem

from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json, file_lock


def device():
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'


def summary(results):
    return {'n': len(results), 'correct': sum(r['success'] for r in results),
                'eye': sum(r['eye_success'] for r in results), 'hand': sum(r['hand_success'] for r in results),
                'order': sum(r['eye_before_hand'] is True for r in results),
                'order_n': sum(r['coordination_eligible'] for r in results),
                'initially_arrived': sum(r['hand_initially_arrived'] for r in results),
                'autonomous_n': sum(r['autonomous_success'] is not None for r in results),
                'autonomous_correct': sum(r['autonomous_success'] is True for r in results),
                'wait_decisions': sum(r['wait_decisions'] for r in results),
                'new_decisions': sum(r['new_decisions'] for r in results),
                'naming_n': sum(r['word_correct'] is not None for r in results),
                'naming_correct': sum(r['word_correct'] is True for r in results)}


def verify_curriculum(work):
    """Freeze generated banks as well as their generating source, before birth."""
    expected={'questions.json':banks()} | {
        f'curricula/{stage}-initial.json':initial(stage) for stage in STAGES}
    manifest=read(work/'curriculum-manifest.json')
    if set(manifest)!=set(expected): raise ValueError('frozen curriculum inventory changed')
    for name, value in expected.items():
        digest=hashlib.sha256(encoded(value)).hexdigest()
        if digest!=manifest[name] or sha(work/name)!=digest:
            raise ValueError('frozen curriculum changed: '+name)


class ClassroomRun:
    def __init__(self, study):
        self.study = study; self.work = study.work; self.device = device()
        self.identity = study.design['subject_identity']
        self.journal = BoundaryJournal(self.work/'subject', self.identity,
             lambda a,p: a.save(p),
             lambda p: EyeHandSystem.restore(p, device=self.device, data_root=self.work),
             lambda a: a.describe(), work=self.work)
        self.a = self.journal.open_current(lambda: EyeHandSystem(identity=self.identity, device=self.device, data_root=self.work))

    def record(self, folder, i, kind, task, rows, data, result, samples):
        put(folder/'clips'/f'{i:06d}.json.gz', gzip.compress(encoded({'kind': kind, 'task': task, 'process': rows}),compresslevel=1,mtime=0))
        fixed_json(folder/'units'/f'{i:06d}.json', result)
        if data is not None:
            stream = io.BytesIO(); np.savez_compressed(stream, **data)
            path = folder/'samples'/f'{i:06d}.npz'; put(path,stream.getvalue())
            ref = {'path': path.relative_to(self.work).as_posix(), 'sha256': sha(path), 'role': kind,
                       'stage': task['stage'], 'lengths': {k:len(v) for k,v in data.items()}}
            self.a.corpora.append(ref)
            fixed_json(folder/'samples'/f'{i:06d}.json',{'samples': samples,'ref': ref})

    def lessons(self, name, tasks, *, teaching=False, collect=False):
        folder = self.work/'stages'/name
        if (folder/'result.json').exists():
            value=read(folder/'result.json')
            self.study.append('stage',name,value)
            self.study.attach(folder/'tasks.json','protocol',name)
            self.study.attach(folder/'result.json','result',name)
            self.study.sync()
            return value
        fixed_json(folder/'tasks.json', tasks)
        if not (folder/'start.json').exists():
            fixed_json(folder/'start.json',{'time_us': self.a.session.engine.time_us,
                'boundary': self.journal.pointer['boundary_sha256'],'wall_epoch': time.time(),'meter': self.a.meter})
        for i,t in enumerate(tasks):
            if t.get('gap_s'):
                key=f'{name}:gap:{i:06d}'
                if key not in self.journal.keys:
                    def gap(a,key=key,t=t,i=i):
                        a.phase=key
                        rows=interval(a,t['gap_s'])
                        put(folder/'clips'/f'gap-{i:06d}.json.gz',gzip.compress(encoded({'kind': 'interval','task': t,'process': rows}),compresslevel=1,mtime=0))
                    self.journal.execute(key,gap)
            if teaching and t.get('reanswer'):
                key=f'{name}:reanswer:{i:06d}'
                if key not in self.journal.keys:
                    def reanswer(a,key=key,t=t,i=i):
                        a.phase=key
                        rows,_,result,_=trial(a,t)
                        put(folder/'clips'/f'reanswer-{i:06d}.json.gz',gzip.compress(encoded({'kind': 'reanswer','task': t,'process': rows}),compresslevel=1,mtime=0))
                        fixed_json(folder/'reanswers'/f'{i:06d}.json',result)
                    self.journal.execute(key,reanswer)
            key=f'{name}:{i:06d}'
            if key in self.journal.keys: continue
            def perform(a,key=key,t=t,i=i):
                a.phase=key; a.cursor+=1
                rows,data,result,samples=trial(a,t,teaching=teaching,collect=collect)
                self.record(folder,i,'teaching' if teaching else 'calibration' if collect else 'test',
                            t,rows,data if teaching or collect else None,result,samples)
            self.journal.execute(key,perform)
        results=[read(folder/'units'/f'{i:06d}.json') for i in range(len(tasks))]
        start=read(folder/'start.json')
        value={'stage': name,'kind': 'teaching' if teaching else 'calibration' if collect else 'test',
                   'identity': self.identity,'start_us': start['time_us'],'end_us': self.a.session.engine.time_us,
                   'wall_seconds': time.time()-start['wall_epoch'],'summary': summary(results),'results': results,
                   'checkpoint': self.journal.pointer['checkpoint'],'boundary': self.journal.pointer['boundary_sha256'],
                   'meter': {k:v-start['meter'].get(k,0) for k,v in self.a.meter.items()}}
        fixed_json(folder/'result.json',value)
        self.study.append('stage',name,value)
        self.study.attach(folder/'tasks.json','protocol',name)
        self.study.attach(folder/'result.json','result',name)
        self.study.sync()
        print(json.dumps({'stage': name,'sim_s': value['end_us']/1e6,'summary': value['summary']},ensure_ascii=False),flush=True)
        return value

    def fit(self,name,head):
        if head not in ('motor','words'): raise ValueError('registered personal peripheral required')
        folder=self.work/'stages'/name
        receipt=folder/f'{head}-result.json'
        if receipt.exists():
            result=read(receipt)
            self.study.append('stage',name+':'+head,result)
            self.study.sync()
            return result
        plan_path=folder/f'{head}-plan.json'
        keys=('x','eye_y','hand_y','move_y') if head=='motor' else ('word_x','word_y')
        if plan_path.exists():
            plan=read(plan_path)
        else:
            self.a.verify_dependencies()
            refs=[]; examples=0
            for ref in self.a.corpora:
                with np.load(self.work/ref['path'],allow_pickle=False) as data:
                    count=len(data[keys[0]])
                if count:
                    refs.append(ref); examples+=count
            plan={'stage': name,'head': head,'identity': self.identity,'inputs': refs,'examples': examples,
                      'start_us': self.a.session.engine.time_us,
                      'start_updates': getattr(self.a,head).computed_updates}
            fixed_json(plan_path,plan)
        if plan['head']!=head or plan['stage']!=name or plan['identity']!=self.identity:
            raise ValueError('calibration plan identity changed')
        last_key=f'{name}:{head}:023'
        if not plan['examples']:
            result={'stage': name,'head': head,'updates': 0,'examples': 0,'computed_updates': plan['start_updates'],
                        'time_us': plan['start_us'],'status': 'no-calibration-data'}
        elif last_key in self.journal.keys:
            # Later stages may already exist. Recover the old receipt from its
            # committed last block, never from the individual's later counters.
            if not all(f'{name}:{head}:{block:03d}' in self.journal.keys for block in range(24)):
                raise ValueError('incomplete calibration block chain')
            final=read(folder/f'{head}-023.json')
            result={'stage': name,'head': head,'updates': 1200,'examples': plan['examples'],
                        'computed_updates': final['computed_updates'],'time_us': final['time_us']}
        else:
            self.a.verify_dependencies()
            arrays={key:[] for key in keys}
            for ref in plan['inputs']:
                path=self.work/ref['path']
                if sha(path)!=ref['sha256']: raise ValueError('frozen calibration input changed')
                with np.load(path,allow_pickle=False) as data:
                    for key, values in arrays.items(): values.append(data[key])
            arrays={key:np.concatenate(values) for key,values in arrays.items()}
            if len(arrays[keys[0]])!=plan['examples']: raise ValueError('calibration example count changed')
            for block in range(24):
                key=f'{name}:{head}:{block:03d}'
                if key in self.journal.keys: continue
                def update(a,key=key,block=block):
                    a.phase=key
                    before=time.perf_counter_ns()
                    if head=='motor': value=a.motor.continue_calibration(**arrays,steps=50)
                    else: value=a.words.continue_calibration(arrays['word_x'],arrays['word_y'],steps=50)
                    a.meter[head+'_calibration_ns']=a.meter.get(head+'_calibration_ns',0)+time.perf_counter_ns()-before
                    fixed_json(folder/f'{head}-{block:03d}.json',value|{'time_us': a.session.engine.time_us})
                self.journal.execute(key,update)
            final=read(folder/f'{head}-023.json')
            result={'stage': name,'head': head,'updates': 1200,'examples': plan['examples'],
                        'computed_updates': final['computed_updates'],'time_us': final['time_us']}
        fixed_json(receipt,result)
        self.study.append('stage',name+':'+head,result)
        self.study.sync()
        return result

    def run(self):
        question_banks=read(self.work/'questions.json')
        birth=self.work/'subject'/'chain'/'000000.json'
        self.study.append('subject','blank-5.1',{'identity': self.identity,'kernel': 'threemind.continuous-memory/5.1',
            'birth': read(birth),'seed': 223,'sensory_seed': 91,'world': 'threemind.grounded-classroom/4',
            'physical_background': True,'full_continuity': True,'previous_subject': None})
        for stage in STAGES:
            self.lessons(stage+'-initial',read(self.work/'curricula'/f'{stage}-initial.json'),teaching=True)
            self.lessons(stage+'-cal-0',question_banks[stage]['cal'],collect=True)
            self.fit(stage+'-fit-0','motor')
            if stage=='semantic': self.fit(stage+'-fit-0','words')
            result=self.lessons(stage+'-dev-0',question_banks[stage]['dev'])
            for r in range(1,4):
                if result['summary']['correct']==result['summary']['n']: break
                tasks=correction(stage,r,result['results'],question_banks[stage]['dev'])
                path=self.work/'curricula'/f'{stage}-correction-{r}.json';fixed_json(path,tasks)
                self.lessons(stage+f'-correction-{r}',tasks,teaching=True)
                # Include exact old-error conditions as well as the fixed general bank.
                calibration=correction_calibration(stage,r,result['results'],
                    question_banks[stage]['dev'],question_banks[stage]['cal'])
                self.lessons(stage+f'-cal-{r}',calibration,collect=True)
                self.fit(stage+f'-fit-{r}','motor')
                if stage=='semantic': self.fit(stage+f'-fit-{r}','words')
                result=self.lessons(stage+f'-dev-{r}',question_banks[stage]['dev'])
        finals={}
        for stage in STAGES:
            finals[stage]=self.lessons(stage+'-final',question_banks[stage]['final'])['summary']
        finals['three-object-transfer']=self.lessons('semantic-transfer',question_banks['semantic']['transfer'])['summary']
        fixed_json(self.work/'computation-complete.json',{'identity': self.identity,'time_us': self.a.session.engine.time_us,
            'latest': self.journal.pointer,'finals': finals,'meter': self.a.meter,'rollback_count': 0})
        self.study.append('result','computation-complete',{'finals': finals,'time_us': self.a.session.engine.time_us})
        self.study.sync()


def prepare(work):
    value={'title': 'E69 连续眼动、手眼协调与形色学习','experiment_date': '2026-10-13',
        'question': '新空白完整个体能否连续学会注视、独立眼手协调和四物体形色回答？',
        'kernel_id': 'threemind.continuous-memory/5.1','subject_identity': 'e69-5.1-223',
        'task_window_s': 6,'question_window_s': 2,'naming_window_s': 1,'decision_interval_s': .5,
        'fixation_dwell_s': .3,'fixation_max_speed_rad_s': .08,'hand_radius_m': .15,
        'correction_rounds': 3,'fit_updates': 1200,'fit_boundary_updates': 50,'core_seed': 223,
        'calibration_tasks_per_stage': 48,'development_tasks_per_round': 24,
        'final_tasks': {'gaze': 24,'coordination': 24,'semantic': 72,'three_object_transfer': 12},
        'maximum_course': {'main_task_entries': 3004,'additional_reanswers': 216,'motor_windows': 3220,
            'naming_questions': 488,'review_gap_s': 288,'simulated_seconds': 20096,'ticks_50ms': 401920,
            'motor_samples': 23256,'word_samples': 320},
        'source_files': ['AGENTS.md','docs/AGENTS.md'],
        'metadata': {'status_at_registration': 'prepared','training_protocol_version': 3,'body_not_reset': True,
                      'control': 'independent-eye-hand-move-wait','word_question_after_fixed_action_window': True}}
    fixed_json(HERE/'design.json',value)
    study=ResearchStudy(work,HERE/'design.json',prepare=True)
    fixed_json(work/'questions.json',banks())
    for stage in STAGES: fixed_json(work/'curricula'/f'{stage}-initial.json',initial(stage))
    paths=[work/'questions.json',*[work/'curricula'/f'{stage}-initial.json' for stage in STAGES]]
    fixed_json(work/'curriculum-manifest.json',{p.relative_to(work).as_posix():sha(p) for p in paths})
    verify_curriculum(work)
    study.attach(work/'curriculum-manifest.json','protocol')
    study.attach(work/'questions.json','protocol')
    for p in (work/'curricula').glob('*.json'): study.attach(p,'protocol')
    study.sync(strict=True);study.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    from threemind_lab.config import load_env
    load_env()
    work=args.work or ResearchStorage().writable_root()/'experiments'/HERE.name
    if args.action=='prepare': prepare(work);return
    with file_lock(work/'runner.lock'):
        study=ResearchStudy(work)
        try:
            study.verify_sources()
            verify_curriculum(work)
            if (work/'computation-complete.json').exists():
                complete=read(work/'computation-complete.json')
                study.append('result','computation-complete',{'finals': complete['finals'],'time_us': complete['time_us']})
                study.sync()
                print('Computation already complete; use read-only postprocessing.');return
            with study.storage.writer(RESOURCE): ClassroomRun(study).run()
        except BaseException as exc:
            atomic_json(work/'host-status.json',{'phase': 'attention-required','error': type(exc).__name__+': '+str(exc),
                                                    'automatic_rollback': False,'pid': os.getpid()})
            raise
        finally: study.close()


if __name__=='__main__':main()
