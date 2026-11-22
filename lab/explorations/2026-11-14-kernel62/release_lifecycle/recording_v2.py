"""Remove repeated whole-state hashing from passive observation, not dynamics."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import time
import importlib.util
from uuid import uuid5

spec=importlib.util.spec_from_file_location('r51t10_recording_helpers',Path(__file__).with_name('study.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

ORIGINAL_OBSERVER=s.observe
ORIGINAL_DRIVER=s.drive
ACTIVE_WORK=None


def observe(e,all_nodes=False):
    nodes=e.observation_nodes()
    return {'time_us':e.time_us,'nodes':nodes if all_nodes else [n for n in nodes if n['channel'] in s.TARGETS]}


def drive(e,case,rows,out=None,mode='observed',backend='native'):
    """Same samples and advancement; wall overruns request a complete boundary."""
    begin=e.time_us;end=case['end_us'];probe=case.get('probe_start_us')
    index=0;points=[];next_point=probe;started=False;changed=False;wall=time.monotonic();pause_requested=False
    stream=None if out is None else gzip.open(out/'course.jsonl.gz','xb',compresslevel=1)
    next_course=begin
    while True:
        if time.monotonic()-wall>=300 and not pause_requested:
            assert ACTIVE_WORK is not None,'calibration exceeded wall budget'
            pause_requested=True
            if not (ACTIVE_WORK/'STOP').exists():
                s.s.write(ACTIVE_WORK/'STOP',{'reason':'stage wall budget; finish current stage before pausing','epoch':time.time()})
        if mode!='plain' and probe is None:observe(e,True)
        if e.life=='dead':break
        if e.time_us==probe and not started and mode!='plain':points.append(observe(e))
        while index<len(rows) and int(rows[index]['source_policy']['resolved_at_us'])==e.time_us:
            e.inject(s.Stimulus.from_dict(rows[index]['stimulus']));index+=1
        e.advance_to(e.time_us)
        if e.time_us==probe and not started:
            started=True
            if mode!='plain':points.append(observe(e))
            next_point+=10000
        elif started and e.time_us==next_point:
            if mode!='plain':points.append(observe(e))
            next_point+=10000
        if stream and e.time_us>=next_course:
            stream.write(json.dumps(observe(e),sort_keys=True).encode()+b'\n');next_course=e.time_us+100000
        if mode in ('restored','paused') and not changed and e.time_us>=begin+1000000:
            image=e.capture_state()
            if mode=='restored':e=s.engine(state=image,backend=backend)
            else:time.sleep(.01)
            assert e.capture_state().digest==image.digest;changed=True
        if e.time_us==end or e.life=='dead':break
        times=[end,e.time_us+(37000 if mode=='partitioned' else 100000)]
        if index<len(rows):times.append(int(rows[index]['source_policy']['resolved_at_us']))
        if next_point is not None:times.append(next_point)
        e.advance_to(min(t for t in times if t>e.time_us))
    if stream:stream.close()
    if e.life!='dead':assert index==len(rows)
    return e,points,index


def verify(work):
    assert not (work/'recording-v2-final-verification.json').exists()
    stage=next(q for q in s.s.read(work/'plan.json') if q['key']=='prefix/p0-f0/0/train')
    case=deepcopy(stage['case']);case['end_us']=8000000
    rows=[r for r in s.load_inputs(work,stage,True) if int(r['source_policy']['resolved_at_us'])<case['end_us']]
    original_targets=s.TARGETS;s.TARGETS={c^0x20000000 for c in original_targets}
    checks=[]
    with tempfile.TemporaryDirectory(dir=s.ROOT/'.work',prefix='r51t10-recording-') as temp:
        for name,flags in s.FLAGS.items():
            for backend in ('reference','native'):
                outputs=[]
                for label,observer in (('original',ORIGINAL_OBSERVER),('v2',observe)):
                    out=Path(temp)/name/backend/label;out.mkdir(parents=True)
                    s.observe=observer
                    e=s.engine({'seed':9291199}|case['initial_config']|flags,backend=backend)
                    driver=ORIGINAL_DRIVER if label=='original' else drive
                    start=time.perf_counter();e,points,n=driver(e,case,rows,out,backend=backend)
                    seconds=time.perf_counter()-start
                    with gzip.open(out/'course.jsonl.gz','rb') as f:course=f.read()
                    outputs.append((e.capture_state().digest,course,seconds))
                assert outputs[0][:2]==outputs[1][:2]
                assert any(p['nodes'] for p in (json.loads(line) for line in outputs[0][1].splitlines()))
                checks.append({'flags':name,'backend':backend,'same_complete_state_and_recording':True,
                               'final_sha256':outputs[0][0],'original_seconds':outputs[0][2],'v2_seconds':outputs[1][2]})
    s.TARGETS=original_targets;s.observe=ORIGINAL_OBSERVER
    s.s.write(work/'recording-v2-final-verification.json',{'passed':True,'independent_codes':True,'checks':checks})
    print(json.dumps(checks),flush=True)


def approve(work):
    assert s.s.read(work/'recording-v2-verification.json')['passed']
    assert not (work/'in-flight.json').exists() and (work/'STOP').exists()
    s.check(work)
    stop=(work/'STOP').read_bytes()
    assert json.loads(stop)['reason']=='boundary pause to remove redundant full-state hashing from passive recorder'
    paths=[Path(__file__),Path(__file__).with_name('recording-amendment.zh.md'),Path(__file__).with_name('recording-amendment.en.md')]
    sources={p.relative_to(s.ROOT).as_posix():s.s.sha(p) for p in paths}
    before=s.s.read(work/'current.json')
    with s.s.base.worker_lock(work),s.pre.client_context() as client:
        assert not (work/'in-flight.json').exists()
        rec=s.s.base.ResearchRecorder(work,s.s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'recording-v2-doc-'+lang)),'request_id':str(uuid5(s.NS,'recording-v2-'+lang)),
                'expected_revision':0,'kind':'note','title':'R51t10 passive recording amendment '+lang,
                'markdown':Path(__file__).with_name('recording-amendment.'+lang+'.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
        for p in paths:rec.save_original('recording-v2-source/'+p.name,p.read_bytes())
        archived=work/'recording-v2-STOP.original.json';archived.write_bytes(stop)
        assert archived.read_bytes()==(work/'STOP').read_bytes()
        s.s.write(work/'recording-v2-frozen.json',{'sources':sources,'boundary':before,'pending':0})
        (work/'STOP').unlink()
    print(json.dumps(before),flush=True)


def run(work):
    global ACTIVE_WORK
    a=s.s.read(work/'recording-v2-frozen.json')
    for rel,h in a['sources'].items():assert s.s.sha(s.ROOT/rel)==h
    s.observe=observe
    s.drive=drive
    ACTIVE_WORK=work
    s.run(work)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('verify','approve','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
