"""Preserve the frozen M5 unit; run each remaining independent source in a fresh host."""
import argparse
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study as original
s = original.s
measure = original.measure
ROOT = original.ROOT
NAME = 'complete-sources-20261113'

def read(p): return json.loads(Path(p).read_bytes())
def receipt_dir(work): return work / 'resumptions' / NAME

def check_idle(work):
    import psutil
    assert not (work / 'in-flight.json').exists()
    host = read(work / 'host.json')
    try:
        p = psutil.Process(host['pid'])
        assert abs(p.create_time() - host['created']) > .001, 'Scientific host is still alive'
    except psutil.NoSuchProcess:
        pass

def verify_prefix(work):
    """No Core construction: check the two complete units and their saved states."""
    assert read(work / 'current.json') == {'completed': 2, 'last': 'o1', 'total': 8}
    result = {}
    for i in range(2):
        folder = work / 'units' / f'o{i}'
        row = read(folder / 'result.json')
        assert row['origin'] == i and row['seed'] == 1056100+i and row['valid']
        def walk(value):
            if isinstance(value, list):
                for item in value: walk(item)
            elif isinstance(value, dict):
                if 'checkpoint' in value:
                    ck = value['checkpoint']; assert s.sha(folder / ck['path']) == ck['sha256']
                for item in value.values(): walk(item)
        walk(row)
        del row; gc.collect()
        files = {}
        for path in sorted(folder.iterdir()):
            assert path.is_file()
            files[path.name] = {'sha256': s.sha(path), 'bytes': path.stat().st_size}
            if path.suffix == '.gz':
                state = json.loads(gzip.decompress(path.read_bytes()))
                assert state['schema'] == 'threemind.m5-process61-whole/1'
                assert state['seed'] == 1056100+i
                assert state['core']['dynamics'] == 'threemind.continuous-memory/6.1'
                assert int(state['core']['time_us']) == state['time_us']
                del state
        assert len([n for n in files if n.endswith('.json.gz')]) == 253
        result[f'o{i}'] = files
        print('verified', f'o{i}', flush=True)
    assert set(p.name for p in (work / 'units').iterdir()) == {'o0', 'o1'}
    return result

def prepare(work):
    original.frozen_check(work)
    check_idle(work)
    dest = receipt_dir(work)
    assert not dest.exists()
    with s.base.worker_lock(work):
        check_idle(work)
        stop_bytes = (work / 'STOP').read_bytes()
        stop = json.loads(stop_bytes)
        assert stop['reason'] == 'pilot process private memory exceeds 1 GiB'
        prefix = verify_prefix(work)
        live = s.base.resource_check(work)
        assert live['available_bytes']['commit'] > 7*2**30
        dest.mkdir(parents=True)
        for name in ('STOP', 'host.json', 'current.json', 'resource-summary.json'):
            shutil.copyfile(work/name, dest/name)
            assert s.sha(work/name) == s.sha(dest/name)
        shutil.copyfile(ROOT / '.work/r51k-host-memory-diagnostic.json', dest/'memory-diagnostic.json')
        s.base.original(dest/'prefix-manifest.json', prefix)
        files = [Path(__file__), HERE/'continuation-note.zh.md', HERE/'continuation-note.en.md']
        s.base.original(dest/'frozen.json', {p.relative_to(ROOT).as_posix(): s.sha(p) for p in files})
        for p in files: shutil.copyfile(p, dest/p.name)
        s.base.original(dest/'preparation.json', {'boundary': 2, 'stop_sha256': hashlib.sha256(stop_bytes).hexdigest(),
            'remaining_origins': list(range(2,8)), 'resources': live, 'Core_engines_loaded': 0,
            'unchanged_scientific_entry': 'measurement.unit', 'private_limit_bytes': 2**30,
            'time_budget_seconds': 7200, 'prior_wall_seconds': read(dest/'resource-summary.json')['wall_seconds']})
        # Register the host-only correction before retiring the resource STOP.
        import httpx
        s.base.load_env()
        with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
            rec = s.base.ResearchRecorder(work, original.PROJECT, client=client)
            rec.resume_recording()
            for lang in ('zh','en'):
                rec.text({'identity': str(uuid5(original.NS, NAME+'-document-'+lang)),
                    'request_id': str(uuid5(original.NS, NAME+'-request-'+lang)), 'expected_revision':0,
                    'kind':'note','title':'R51k complete-source host continuation '+lang,
                    'markdown': (HERE/f'continuation-note.{lang}.md').read_text('utf-8')})
            rec.synchronize(strict=True)
            assert rec.status['pending'] == 0
        assert (work/'STOP').read_bytes() == stop_bytes
        check_idle(work)
        (work/'STOP').unlink()
        s.base.original(dest/'retirement.json', {'exact_stop_sha256': hashlib.sha256(stop_bytes).hexdigest(),
            'epoch':time.time(), 'complete_sources':2, 'pending':0})
    print('prepared complete boundary 2; remaining sources not started', flush=True)

def continuation_check(work):
    original.frozen_check(work)
    dest=receipt_dir(work)
    assert (dest/'retirement.json').exists()
    for rel, sha in read(dest/'frozen-v2.json').items(): assert s.sha(ROOT/rel)==sha
    assert not (work/'STOP').exists() and not (work/'in-flight.json').exists()

def finish_preparation(work):
    """Complete only the interrupted journal registration; preserve its first attempt."""
    import httpx
    original.frozen_check(work)
    dest=receipt_dir(work)
    assert not (dest/'retirement.json').exists()
    with s.base.worker_lock(work):
        check_idle(work)
        expected=read(dest/'preparation.json')['stop_sha256']
        assert s.sha(work/'STOP')==expected==s.sha(dest/'STOP')
        for unit, files in read(dest/'prefix-manifest.json').items():
            for name, metadata in files.items(): assert s.sha(work/'units'/unit/name)==metadata['sha256']
        assert read(work/'current.json')['completed']==2
        assert s.base.resource_check(work)['available_bytes']['commit']>7*2**30
        files=[Path(__file__),HERE/'continuation-note.zh.md',HERE/'continuation-note.en.md']
        s.base.original(dest/'frozen-v2.json',{p.relative_to(ROOT).as_posix():s.sha(p) for p in files})
        shutil.copyfile(Path(__file__),dest/'continue_complete_sources-v2.py')
        s.base.original(dest/'preparation-correction.json',{'reason':'resume_recording was missing before attaching notes',
            'scientific_sources_advanced':0,'first_preparation_preserved':True,'original_STOP_retained_until_registration':True})
        s.base.load_env()
        with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
                password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
                transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
            rec=s.base.ResearchRecorder(work,original.PROJECT,client=client);rec.resume_recording()
            assert rec.experiment==read(work/'registration.json')['record']
            for lang in ('zh','en'):
                rec.text({'identity':str(uuid5(original.NS,NAME+'-document-'+lang)),
                    'request_id':str(uuid5(original.NS,NAME+'-request-'+lang)),'expected_revision':0,
                    'kind':'note','title':'R51k complete-source host continuation '+lang,
                    'markdown':(HERE/f'continuation-note.{lang}.md').read_text('utf-8')})
            rec.synchronize(strict=True);assert rec.status['pending']==0
        check_idle(work);assert s.sha(work/'STOP')==expected
        (work/'STOP').unlink()
        s.base.original(dest/'retirement.json',{'exact_stop_sha256':expected,'epoch':time.time(),'complete_sources':2,'pending':0})
    print('prepared complete boundary 2; remaining sources not started',flush=True)

def one(work, i):
    import psutil
    continuation_check(work)
    assert i in range(2,8)
    current=read(work/'current.json')
    assert current['completed']==i and current['last']==f'o{i-1}'
    folder=work/'units'/f'o{i}'
    assert not folder.exists()
    completed_time=read(receipt_dir(work)/'preparation.json')['prior_wall_seconds']
    for p in (receipt_dir(work)/'hosts').glob('o*.json'):
        completed_time += read(p)['wall_seconds']
    assert completed_time < 7200
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json', {'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        s.base.original(work/'in-flight.json', {'unit':f'o{i}','pid':os.getpid(),'created':psutil.Process().create_time()})
        result=measure.unit(folder,i)
        s.base.original(folder/'result.json',result)
        (work/'in-flight.json').unlink()
        s.base.atomic_json(work/'current.json', {'completed':i+1,'total':8,'last':f'o{i}'})
        reason=('invalid matching or continuity' if not result['valid'] else
                'source originals budget' if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) > original.RAW_CAP/8 else
                'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > original.RAW_CAP else
                'cumulative two-hour budget' if completed_time+time.monotonic()-guard.started>7200 else None)
        if reason and not (work/'STOP').exists(): s.base.original(work/'STOP', {'reason':reason,'complete_boundary':f'o{i}'})
    resources=read(work/'resource-summary.json')
    s.base.original(receipt_dir(work)/'hosts'/f'o{i}.json', resources|{'host':read(work/'host.json'), 'complete_source':i})
    print('complete',f'o{i}',flush=True)

def run(work):
    continuation_check(work)
    dest=receipt_dir(work)
    assert not (dest/'coordinator.json').exists()
    (dest/'hosts').mkdir()
    (dest/'logs').mkdir()
    s.base.original(dest/'coordinator.json',{'pid':os.getpid(),'command':sys.argv,'epoch':time.time()})
    for i in range(2,8):
        if (work/'STOP').exists() or (work/'in-flight.json').exists():break
        with (dest/'logs'/f'o{i}.stdout.log').open('xb') as out, (dest/'logs'/f'o{i}.stderr.log').open('xb') as err:
            child=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'one','--work',str(work),'--origin',str(i)],stdout=out,stderr=err)
        print('host completed',i,'exit',child.returncode,flush=True)
        if child.returncode or (work/'STOP').exists():break
    rows=[read(dest/'resource-summary.json')]+[read(p) for p in sorted((dest/'hosts').glob('o*.json'))]
    resources={'peak_private_bytes':max(r['peak_private_bytes'] for r in rows),
        'minimum_available_bytes':{k:min(r['minimum_available_bytes'][k] for r in rows) for k in rows[0]['minimum_available_bytes']},
        'wall_seconds':sum(r['wall_seconds'] for r in rows), 'host_epochs':len(rows), 'initial_budget_stop_preserved':True}
    s.base.atomic_json(work/'resource-summary.json',resources)
    if read(work/'current.json')['completed']==8 and not (work/'STOP').exists():
        s.base.original(work/'summary.json',{'status':'awaiting-analysis','origins':8,'readout_conditions':['temporal','endpoint'],
            'wall_seconds':resources['wall_seconds'],'complete_source_host_continuation':NAME})
    else:
        print('paused; preserve STOP and all evidence',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','finish-preparation','run','one'])
    p.add_argument('--work',type=Path,required=True);p.add_argument('--origin',type=int)
    a=p.parse_args();w=a.work.resolve()
    if a.action=='one':one(w,a.origin)
    else:{'prepare':prepare,'finish-preparation':finish_preparation,'run':run}[a.action](w)
