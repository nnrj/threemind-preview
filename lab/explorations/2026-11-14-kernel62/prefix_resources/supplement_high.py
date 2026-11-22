"""Prospective bounded extension: keep the prior 0.004 gate while replenishing resources."""
import argparse
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid5
sys.path.insert(0,str(Path(__file__).parent))
import study_resources as x
s=x.s
CONDITIONS={
 'high-current-fast':{'mode':'stable','patch':{'activation_signal_threshold':.004,'stp_recovery_tau_s':.08}},
 'high-current-full':{'mode':'stable','patch':{'activation_signal_threshold':.004,'depletion_enabled':False}},
 'high-old-fast':{'mode':'old','patch':{'activation_signal_threshold':.004,'stp_recovery_tau_s':.08}},
 'high-old-full':{'mode':'old','patch':{'activation_signal_threshold':.004,'depletion_enabled':False}},
}


def register(work):
    x.check(work)
    assert not (work/'supplement-frozen.json').exists()
    # The primary driver runs in another process; this registry extension is local to this script.
    for name,item in CONDITIONS.items():
        cfg=x.r.ResearchConfig(**(s.STABLE|item['patch']),research_transport='old-inhibition',resource_precheck=False)
        assert cfg.activation_signal_threshold==.004
    with x.previous.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(x.NS,'high-note-'+lang)),'request_id':str(uuid5(x.NS,'high-note-request-'+lang)),
                'expected_revision':0,'kind':'note','title':'R51t9 prospective high-threshold supplement '+lang,
                'markdown':(x.HERE/f'supplement-high.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
    s.write(work/'supplement-frozen.json',{'conditions':CONDITIONS,'stages':24,
        'sources':{p.relative_to(x.ROOT).as_posix():s.sha(p) for p in [Path(__file__),x.HERE/'supplement-high.zh.md',x.HERE/'supplement-high.en.md']},
        'epoch':time.time(),'primary_progress_at_registration':s.read(work/'current.json')})
    print(json.dumps({'supplement_registered':True,'pending':0}),flush=True)


def run(work):
    x.check(work)
    assert (work/'summary.json').exists() and not any((work/p).exists() for p in ('in-flight.json','STOP','supplement-summary.json'))
    f=s.read(work/'supplement-frozen.json')
    for rel,h in f['sources'].items():assert s.sha(x.ROOT/rel)==h
    x.VARIANTS.update(CONDITIONS)
    index=s.read(work/'cases.json');results=[]
    import psutil
    with s.base.worker_lock(work),x.previous.Guard(work) as guard:
        receipt={'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv}
        s.write(work/f'host-supplement-{time.time_ns()}.json',receipt);s.base.atomic_json(work/'host.json',receipt)
        for name in CONDITIONS:
            for block in (0,1):
                for cue in ('train','AB','DB'):
                    out=x.folder(work,name,block,cue);key=f'{name}/{block}/{cue}'
                    if (out/'result.json').exists():
                        q=s.read(out/'result.json');assert x.state_at(out,'final').digest==q['final_sha256'];results.append(q);continue
                    if (work/'STOP').exists():return
                    assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
                    out.mkdir(parents=True,exist_ok=False)
                    s.write(work/'in-flight.json',{'key':key,'pid':os.getpid(),'created':psutil.Process().create_time()})
                    case=index[f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}']
                    parent=None if cue=='train' else x.state_at(x.folder(work,name,block,'train'),'final')
                    e=x.create(name,case,state=parent)
                    if parent is not None:e.reconfigure(replace(e.config,**(case['patch']|CONDITIONS[name]['patch'])))
                    before=e.capture_state();x.previous.put(out/'initial.rstate.gz',before)
                    trace=x.c.Trace(out/'teaching.jsonl.gz') if cue=='train' else None
                    t=time.monotonic();points=x.c.execute(e,case,s.inputs(work,case),trace)
                    if trace:trace.close()
                    after=e.capture_state();x.previous.put(out/'final.rstate.gz',after)
                    assert x.state_at(out,'final').digest==after.digest
                    if cue!='train':s.packed(out/'process.json.gz',points)
                    q={} if cue=='train' else s.measure.process(case,points)
                    q.update(key=key,variant=name,block=block,cue=cue,kernel=after.to_dict()['dynamics'],
                        initial_sha256=before.digest,final_sha256=after.digest,parent_sha256=parent.digest if parent else None,
                        time_us=e.time_us,wall_seconds=time.monotonic()-t)
                    s.write(out/'result.json',q);results.append(q);(work/'in-flight.json').unlink()
                    s.base.atomic_json(work/'supplement-current.json',{'complete':len(results),'total':24,'last':key})
                    print(json.dumps({'supplement_complete':len(results),'key':key,'margin':q.get('signed_peak')}),flush=True)
                    del e,points;gc.collect()
        s.write(work/'supplement-summary.json',{'stages':len(results),'results':results})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
