"""E27: bounded, reproducible survival, physical-food accounting and lineage."""

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import psutil
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))

from lab.tools.service_study import Study,StudyConfig,encoded,new_json,read_json
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth

from physical import defaults
from session import SurvivalSession

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/survival-transfer-20261002'


class SurvivalStudy(Study):
    def note(self,key,title,text):
        # Notebook URLs have a deliberately narrower contract than repo Markdown.
        # Resolve the two design links to the fixed, existing source revision.
        def link(match):
            target=match[1]
            if target.startswith(('http:','https:','#','/')): return match[0]
            path=(HERE/target).resolve().relative_to(ROOT).as_posix()
            return '](https://github.com/nnrj/threemind/blob/5f27cef/'+path+')'
        return super().note(key,title,re.sub(r'\]\(([^)]+)\)',link,text))

    def guard(self,force=False):
        super().guard(force)
        if shutil.disk_usage('C:/').free<8*2**30 or shutil.disk_usage('E:/').free<30*2**30:
            raise RuntimeError('survival-study disk reserve')
        if time.monotonic()-getattr(self,'last_process_check',0)>30:
            total=0
            for p in psutil.process_iter(['cmdline','memory_info']):
                try:
                    c=p.info['cmdline'] or []
                    if len(c)>1 and c[1].replace('\\','/').endswith('2026-10-02-survival-transfer/experiment.py'):
                        total+=p.info['memory_info'].rss
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            if total>4*2**30: raise RuntimeError('aggregate simulation processes exceed 4 GiB')
            self.last_process_check=time.monotonic()
        if time.monotonic()-getattr(self,'last_aggregate_check',0)>1:
            completed=0.
            active=0.
            for case in (WORK/'cases').iterdir():
                if (case/'result.json').exists(): completed+=read_json(case/'result.json')['wall_seconds']
                elif (case/'resource.json').exists():
                    record=read_json(case/'resource.json')
                    if psutil.pid_exists(record['pid']): active+=max(0.,time.time()-record['started_epoch'])
            if completed+active>=self.settings.wall_seconds:
                raise RuntimeError('aggregate concurrent simulation budget')
            self.last_aggregate_check=time.monotonic()


def study(prepare=False):
    return SurvivalStudy(StudyConfig('survival-transfer/1','E27 自行抓杯、颗粒转移与有限供能生存选择',
        HERE,WORK,12,instance_limit=128,wall_seconds=14400,storage_soft=8*2**30,
        storage_hard=10*2**30,usage_soft_delta=5,usage_hard_delta=8),prepare=prepare)


def freeze():
    cost=read_json(ROOT/'.work/survival-cost-01/result.json')
    assert cost['exact_restore'] and cost['read_only']
    control=read_json(ROOT/'.work/survival-engineering-03/result.json')
    assert control['transferred']>0 and control['grasp'] and control['lift']
    rows=cost['rows']
    rate=(rows[19]['core']['energy']['reserve']-rows[29]['core']['energy']['reserve'])/10
    initial=math.ceil(rate*240/100)*100
    food=math.ceil(rate*60/100)*100
    recovering=(WORK/'platform.json').exists()
    s=study(not recovering)
    if recovering:
        if (WORK/'frozen.json').exists(): raise RuntimeError('formal registration already frozen')
        for language in ('zh','en'):
            source=HERE/f'design.{language}.md'
            s.note(f'design:{language}',f'执行登记 / Study registration {language}',source.read_text(encoding='utf-8'))
            target=WORK/f'design-frozen.{language}.md'
            if not target.exists(): shutil.copy2(source,target)
        for name in s.implementation['source_files']:
            target=WORK/'frozen-sources'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists(): shutil.copy2(ROOT/name,target)
        new_json(WORK/'registration-recovery.json',dict(reason='notebook refused relative Markdown URL; fixed source links, no simulation started',
            project=s.project,source_design_unchanged=True))
    calibration=WORK/'engineering'
    calibration.mkdir()
    for name in ('survival-engineering-01','survival-engineering-02','survival-engineering-03','survival-cost-01'):
        shutil.copytree(ROOT/'.work'/name,calibration/name)
    s.note('numerical-freeze','正式候选数值冻结',
        f'正式候选前冻结：30 秒工程校准末 10 秒平均耗能 {rate:.6f} 实验单位/秒。'
        f'出生储备按 240 秒计算并向上取整为 {initial}，每颗有效转移供能 {food}，'
        f'容量 {4*initial}；每 1 模拟秒结算。600 模拟秒/个体；无免费补给；每30秒外部补料但不复位机械臂与内核。'
        '末日未获繁殖资格的活体暂停保存。原始力矩、无IK、无示教；视觉16×12、10Hz，'
        '其余感官50Hz、物理500Hz。独立工程控制器已完成9/12颗转移，不属于ThreeMind结果。')
    new_json(WORK/'frozen.json',dict(schema='threemind.granular-registration/1',
        duration_us=600000000,per_case_wall_seconds=900,initial_energy=initial,
        energy_capacity=4*initial,energy_per_grain=food,food_interval_us=1000000,
        calibration_rate=rate,maximum_founders=32,first_founders=16,
        fallback_founders=8,descendant_generations=2,descendants_per_generation=16,
        primary_seeds=[270100+i for i in range(32)],
        environment_seeds=[271100+i for i in range(32)],
        rationale='240 seconds initial and 60 seconds per grain at measured late calibration cost; no candidate-based tuning',
        source_calibration_sha256=hashlib.sha256(encoded(cost)).hexdigest(),
        source_physics=control['xml_hash']))
    new_json(WORK/'usage.json',{'used_percent':12,'source':'account check before formal simulation'})
    print(json.dumps({'prepared':s.project,'initial_energy':initial,'energy_per_grain':food,'rate':rate}))


def make_protocol(seed,environment_seed,attached=False):
    f=read_json(WORK/'frozen.json')
    return dict(schema='threemind.granular-survival/1',world=defaults()|
        dict(seed=seed,environment_seed=environment_seed,attached=attached),
        core=dict(seed=seed,energy_simulation_enabled=True,energy_starvation_damage_enabled=True,
            energy_initial_reserve=f['initial_energy'],energy_capacity=f['energy_capacity']),
        food_interval_us=f['food_interval_us'],energy_per_grain=f['energy_per_grain'])


def run_case(s,key,protocol,*,parent_key=None,generation=0):
    folder=WORK/'cases'/key
    if (folder/'result.json').exists(): return read_json(folder/'result.json')
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError('partial trial retained; explicit recovery is required: '+key)
    s.completed_count=None
    s.guard(True)
    folder.mkdir(parents=True,exist_ok=True)
    image=None
    parent_hash=None
    if parent_key:
        parent_folder=WORK/'cases'/parent_key
        parent=read_json(parent_folder/'result.json')
        if parent['status']!='survived': raise ValueError('only surviving parents may reproduce')
        parent_state=ArtifactCodec.decode((parent_folder/'final.tmind').read_bytes())
        parent_hash=parent_state.digest
        image=birth(parent_state)
    started=time.monotonic()
    new_json(folder/'resource.json',{'pid':os.getpid(),'started_epoch':time.time()})
    s.active_case=SimpleNamespace(born_wall=started)
    frozen=read_json(WORK/'frozen.json')
    error=None
    status='running'
    task_events=[]
    first_empty=None
    trajectory=[]
    with SurvivalSession(protocol,image=image) as session:
        initial=session.engine.capture_state()
        (folder/'initial.tmind').write_bytes(ArtifactCodec.encode(initial))
        new_json(folder/'protocol.json',dict(protocol=protocol,registration=frozen,
            parent_key=parent_key,parent_hash=parent_hash,generation=generation,
            initial_hash=initial.digest,runner_signature=s.runner_signature,
            physical_xml_hash=session.world.xml_hash))
        last_report=time.monotonic()
        with gzip.open(folder/'events.jsonl.gz','xb',compresslevel=3) as stream:
            def record(row):
                task_events.extend(row['world_events'])
                stream.write(encoded(row)+b'\n')
            try:
                while session.engine.time_us<frozen['duration_us'] and session.engine.life!='dead':
                    s.guard()
                    if time.monotonic()-started>frozen['per_case_wall_seconds']:
                        status='censored-wall-budget'
                        break
                    session.step(record)
                    if session.world.time_us%1000000==0 or session.engine.life=='dead':
                        row=session.metrics()
                        trajectory.append(row)
                        if first_empty is None and row['core']['energy']['reserve']<=1e-9:
                            first_empty=row['time_us']
                    if time.monotonic()-last_report>30:
                        print(json.dumps({'case':key,'sim_seconds':session.engine.time_us/1e6,
                            'energy':session.engine.metrics()['energy']['reserve'],
                            'transferred':session.world.transferred,'wall_seconds':time.monotonic()-started}),flush=True)
                        last_report=time.monotonic()
                if status=='running':
                    status=('starved' if first_empty is not None else 'core-dead-other') if session.engine.life=='dead' else (
                        'survived' if session.engine.life=='active' else 'never-activated')
            except Exception as exc:
                status='failed-or-resource-stopped'
                error=type(exc).__name__+': '+str(exc)
            final=session.engine.capture_state()
            (folder/'final.tmind').write_bytes(ArtifactCodec.encode(final))
            new_json(folder/'context.json',session.context())
        new_json(folder/'trajectory.json',trajectory)
        result=dict(key=key,status=status,error=error,parent_key=parent_key,parent_hash=parent_hash,
            generation=generation,attached=protocol['world']['attached'],seed=protocol['world']['seed'],
            environment_seed=protocol['world']['environment_seed'],initial_hash=initial.digest,final_hash=final.digest,
            first_empty_us=first_empty,metrics=session.metrics(),events=task_events,
            wall_seconds=time.monotonic()-started,runner_signature=s.runner_signature)
        new_json(folder/'result.json',result)
    s.active_case=None
    print(json.dumps({'case':key,'status':status,'seconds':result['metrics']['time_us']/1e6,
        'transferred':result['metrics']['transferred'],'remaining_energy':result['metrics']['core']['energy']['reserve'],
        'wall_seconds':result['wall_seconds'],'error':error}),flush=True)
    if error: raise RuntimeError(error)
    return result


def run_founders(count,start=0):
    f=read_json(WORK/'frozen.json')
    if not 1<=count<=f['maximum_founders']: raise ValueError('founder count exceeds registration')
    s=study()
    if not 0<=start<count: raise ValueError('invalid founder range')
    for i in range(start,count):
        if i>=f['first_founders']: s.allow_extension()
        run_case(s,f'free-g0-{i:03d}',make_protocol(f['primary_seeds'][i],f['environment_seeds'][i]))


def fallback(start=0,count=8):
    s=study()
    founders=[read_json(p) for p in (WORK/'cases').glob('free-g0-*/result.json')]
    if len(founders)<16 or any(r['metrics']['transferred'] for r in founders):
        raise ValueError('attached-cup secondary requires at least 16 primary cases and zero qualified transfers')
    if not 0<=start<count<=read_json(WORK/'frozen.json')['fallback_founders']:
        raise ValueError('fallback range exceeds registration')
    for i in range(start,count):
        s.allow_extension()
        run_case(s,f'attached-g0-{i:03d}',make_protocol(270100+i,271100+i,True))


def reproduce(prefix,generation):
    f=read_json(WORK/'frozen.json')
    if generation not in (1,2): raise ValueError('two descendant generations registered')
    s=study()
    previous=[read_json(p) for p in (WORK/'cases').glob(f'{prefix}-g{generation-1}-*/result.json')]
    if not previous: raise ValueError('parent generation absent')
    living=sorted([r for r in previous if r['status']=='survived'],
        key=lambda r:(-r['metrics']['core']['energy']['reserve'],r['key']))
    selected=living[:max(1,len(living)//4)]
    allocation=[]
    for i in range(f['descendants_per_generation'] if selected else 0):
        parent=selected[i%len(selected)]
        allocation.append(dict(key=f'{prefix}-g{generation}-{i:03d}',parent=parent['key'],
            seed=parent['seed'],environment_seed=272000+generation*100+i))
    decision=dict(generation=generation,prefix=prefix,alive=[r['key'] for r in living],
        parents=[r['key'] for r in selected],paused_not_selected=[r['key'] for r in living if r not in selected],
        extinct=not living,allocation=allocation,
        criterion='remaining energy at time limit; death was exclusively Core lifecycle, no rank-based forced killing')
    path=WORK/f'lineage-{prefix}-g{generation}.json'
    if path.exists(): assert read_json(path)==decision
    else: new_json(path,decision)
    print(json.dumps(decision),flush=True)
    for child in allocation:
        s.allow_extension()
        run_case(s,child['key'],make_protocol(child['seed'],child['environment_seed'],prefix=='attached'),
            parent_key=child['parent'],generation=generation)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    a=sub.add_parser('founders'); a.add_argument('--count',type=int,default=16); a.add_argument('--start',type=int,default=0)
    a=sub.add_parser('fallback'); a.add_argument('--start',type=int,default=0); a.add_argument('--count',type=int,default=8)
    a=sub.add_parser('reproduce'); a.add_argument('--prefix',choices=['free','attached'],default='free'); a.add_argument('--generation',type=int,default=1)
    a=p.parse_args()
    if a.command=='prepare': freeze()
    elif a.command=='founders': run_founders(a.count,a.start)
    elif a.command=='fallback': fallback(a.start,a.count)
    else: reproduce(a.prefix,a.generation)
