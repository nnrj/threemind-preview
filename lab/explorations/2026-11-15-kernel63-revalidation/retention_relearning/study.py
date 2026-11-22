"""R63u registration, guarded apparatus, independent calibration and formal run."""
import argparse
import gc
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT/'src')]
import support as s
import retention_rig as g
import measurement
import scoring
from allocation import disk_allocation

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('9c014271-0e32-5cd8-881d-98b045d8bd55')
RAW_CAP = 2*2**30


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def allocated(path):
    return sum(disk_allocation(p)['allocated_bytes'] for p in path.rglob('*') if p.is_file())


def table():
    return [{'origin': origin, 'seed': g.case_seed('X2', origin, delay), 'delay': delay, 'mode': mode,
             'key': f'd{delay}-o{origin}-{mode}'}
            for delay in g.DELAYS for origin in range(8) for mode in g.MODES]


def frozen_check(work):
    frozen = read(work/'frozen.json')
    for rel, sha in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT/rel) == sha, rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == frozen['native_sha256']
    assert s.sha(work/'cases.json') == frozen['cases_sha256']
    assert read(work/'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    for batch in ('transfer-63-rerun-v1', 'memory-timescales-63-rerun-v1'):
        done = read(work.parent/batch/'publication/completion.json')
        assert done['coverage'] == 'verified' and done['pending'] == 0 and not done['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 31.125*2**30
    from verify_measurement import verify
    checked = verify()
    assert checked['passed']
    work.mkdir()
    s.base.original(work/'cases.json', table())
    s.base.original(work/'measurement-check.json', checked)
    paths = sorted(HERE.glob('*.py')) + sorted(HERE.glob('protocol.*.md'))
    paths += [HERE.parent/'criteria/rig.py', HERE.parent/'support.py', HERE.parent/'allocation.py',
              ROOT/'lab/tools/study_lock.py',
              ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    old = ROOT/'lab/explorations/2026-10-16-mechanism-discovery'
    paths += [old/name for name in ('pilot_m1.py','pilot_m2.py','pilot_m3.py','closure_rig.py','closure_driver.py','closure_analyze.py')]
    from _threemind_native import _threemind_native as native
    frozen = {'kernel': g.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': read(work.parent/'criteria-63-rerun-v1/frozen.json')['production_sources'],
              'cases_sha256': s.sha(work/'cases.json'), 'formal_origins': 32, 'configuration_units': 64,
              'calibration_seeds': [1026002,1026003], 'apparatus_seed': 1026001}
    s.base.original(work/'frozen.json', frozen)
    for p in paths:
        dest = work/'frozen-source'/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key':'r63u:retention-relearning:6.3:20261116:v1',
                      'title':'R63u：6.3连接保存、提示提取与再学习',
                      'classification':'formal','execution_status':'running','executor':'ai','kernels':[g.KERNEL],
                      'protocol':(HERE/'protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
                      'required_roles':['protocol','report','note','original'],
                      'metadata':{'origins_per_delay':8,'independent_origins':32,'configuration_units':64,
                                  'delays':[1,30,60,300],'independent_calibration_before_formal_births':True}},
                     request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                      'expected_revision':0,'kind':'protocol','title':'R63u protocol '+lang,
                      'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        result={'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
        print(json.dumps(result),flush=True)


def apparatus(work):
    import psutil
    from analyze import Audit
    frozen_check(work)
    assert not any((work/n).exists() for n in ('apparatus.json','STOP','in-flight.json'))
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        results=[]
        for mode in g.MODES:
            parent=g.Rig('threemind',1026001,mode)
            g.teaching(parent,0,delay=1)
            folder=work/'apparatus'/mode
            parent_receipt=measurement.save(folder,'parent',parent)
            audit=Audit()
            initial=audit.state(folder,parent_receipt,1026001,mode)
            hashes={}
            for reading in ('plain','observed','restored','paused'):
                child=g.Rig.restore(parent.save())
                answer=g.probe(child,'X',.8,frequent=reading=='observed',restore_mid=reading=='restored',pause_mid=reading=='paused')
                receipt=measurement.save(folder,reading,child)
                final=audit.state(folder,receipt,1026001,mode)
                audit.probe(initial,final,answer,'X',.8)
                hashes[reading]=g.m.digest(child.save())
                assert answer['trace_count']==1500
                del child
            assert len(set(hashes.values()))==1
            results.append({'mode':mode,'hashes':hashes,'independent_probe_audits':audit.probes,
                            'maximum_decimal_error':audit.error})
        result={'passed':True,'scientific_origins':0,'results':results}
        s.base.original(work/'apparatus.json',result)
        (work/'in-flight.json').unlink()
    s.base.original(work/'apparatus-resources.json',read(work/'resource-summary.json'))
    print(json.dumps(result),flush=True)


def calibrate(work):
    import psutil
    from analyze import Audit
    frozen_check(work)
    assert read(work/'apparatus.json')['passed']
    assert not any((work/n).exists() for n in ('calibration.json','calibration','units','STOP','in-flight.json'))
    rows=[]
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        for mode in g.MODES:
            for seed in (1026002,1026003):
                for history in (0,1):
                    assert guard.thread.is_alive()
                    if (work/'STOP').exists():return
                    key=f'{mode}-s{seed}-h{history}'
                    s.base.original(work/'in-flight.json',{'phase':'calibration','key':key,
                        'pid':os.getpid(),'created':psutil.Process().create_time()})
                    result=measurement.calibration_case(work/'calibration'/key,seed,mode,history)
                    audit=Audit()
                    folder=work/'calibration'/key
                    birth,initial,final=[audit.state(folder,result[k],seed,mode) for k in ('birth','initial','final')]
                    audit.teaching(birth,initial,seed,history,30,False)
                    assert audit.course(initial,final,result['course'],history,None,True)==result['values']
                    s.base.original(work/'calibration'/key/'result.json',result)
                    rows.append(result)
                    (work/'in-flight.json').unlink()
                    print('calibrated',key,flush=True)
                    gc.collect()
        selection=scoring.calibrate(rows)
        # Budget all formal courses at the largest observed full 16-round course.
        course_bytes=max(allocated(work/'calibration'/f'{r["mode"]}-s{r["seed"]}-h{r["history"]}') for r in rows)
        estimated_unit=max(2**20,course_bytes*8)*1.25
        estimate=allocated(work)+64*estimated_unit+128*2**20
        budget={'calibration_max_course_bytes':course_bytes,'unit_estimate_bytes':estimated_unit,
                'estimated_original_bytes':estimate,'raw_cap_bytes':RAW_CAP,'within_cap':estimate<RAW_CAP,
                'formal_births':0,'maximum_new_course_rounds':16}
        s.base.original(work/'calibration.json',{'rows':rows,'selections':selection,
                                               'frozen_before_formal_births':True})
        s.base.original(work/'budget.json',budget)
        if not budget['within_cap']:
            s.base.original(work/'STOP',{'reason':'calibrated complete budget exceeds cap','complete_boundary':'calibration'})
    s.base.original(work/'calibration-resources.json',read(work/'resource-summary.json'))
    print(json.dumps({'selections':selection,'budget':budget}),flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert not any((work/n).exists() for n in ('units','summary.json','STOP','in-flight.json'))
    assert read(work/'apparatus.json')['passed'] and read(work/'budget.json')['within_cap']
    calibration=read(work/'calibration.json')
    assert calibration['frozen_before_formal_births']
    assert shutil.disk_usage(work).free>31.125*2**30
    s.base.original(work/'formal-freeze.json',{'calibration_sha256':s.sha(work/'calibration.json'),
                                              'budget_sha256':s.sha(work/'budget.json')})
    wall=time.monotonic()
    completed=[]
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in read(work/'cases.json'):
            if (work/'STOP').exists():break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            folder=work/'units'/case['key']
            assert not folder.exists()
            s.base.original(work/'in-flight.json',{'unit':case['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            began=time.monotonic()
            result=measurement.unit(folder,case,calibration['selections'])
            result['wall_seconds']=time.monotonic()-began
            s.base.original(folder/'result.json',result)
            (work/'in-flight.json').unlink()
            completed.append(case['key'])
            s.base.atomic_json(work/'current.json',{'completed':len(completed),'total':64,'last':case['key']})
            cost=allocated(folder)
            reason=('unit cost exceeds frozen estimate by 50%' if cost>1.5*read(work/'budget.json')['unit_estimate_bytes'] else
                    'originals cap' if allocated(work)>RAW_CAP else
                    'two-hour budget' if time.monotonic()-wall>7200 else None)
            if reason and not (work/'STOP').exists():
                s.base.original(work/'STOP',{'reason':reason,'complete_boundary':case['key'],'allocated_unit_bytes':cost})
            print(json.dumps({'completed':len(completed),'total':64,'unit':case['key']}),flush=True)
            del result
            gc.collect()
        if len(completed)==64:
            s.base.original(work/'summary.json',{'status':'awaiting-analysis','independent_origins':32,
                'configuration_units':64,'wall_seconds':time.monotonic()-wall})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','apparatus','calibrate','run'))
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    globals()[args.action](args.work.resolve())
