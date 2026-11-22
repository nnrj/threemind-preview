"""Bounded supplementary tails without a configuration-time settlement."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time
from uuid import uuid5

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t10_birth_tail_helpers',HERE/'study.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
DELAYS=(0,1,5,10,30,60,120,300)


def register(work):
    s.check(work)
    assert s.s.read(work/'summary.json')['stages']==92
    assert not any((work/n).exists() for n in ('in-flight.json','STOP','tail-birth-frozen.json'))
    parents={}
    for flags in s.FLAGS:
        for block in (0,1):
            key=f'prefix/{flags}/{block}/train'
            parent=s.get(work/'cases'/key/'final.rstate.gz')
            assert parent.digest==s.s.read(work/'cases'/key/'result.json')['final_sha256']
            parents[key]=parent.digest
    sources={p.relative_to(s.ROOT).as_posix():s.s.sha(p) for p in
             (Path(__file__),HERE/'tail_birth.zh.md',HERE/'tail_birth.en.md')}
    frozen={'parents':parents,'sources':sources,'additional_stages':8,'additional_original_cap':32*2**20,
            'host_wall_seconds':600,'tail_wall_seconds':300,'no_reconfigure':True,'date':'2026-11-15'}
    with s.pre.client_context() as client:
        rec=s.s.base.ResearchRecorder(work,s.s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'birth-tail-protocol-doc-'+lang)),
                      'request_id':str(uuid5(s.NS,'birth-tail-protocol-'+lang)),
                      'expected_revision':0,'kind':'protocol','title':'R51t10 no-reconfiguration tail supplement '+lang,
                      'markdown':(HERE/f'tail_birth.{lang}.md').read_text('utf8')})
        rec.append('stage','r51t10:birth-tail:registration',frozen,request_id=uuid5(s.NS,'birth-tail-register'))
        rec.synchronize(strict=True);assert rec.status['pending']==0
    for rel in sources:
        dest=work/'tail-birth-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(s.ROOT/rel,dest)
    s.s.write(work/'tail-birth-frozen.json',frozen)
    print(json.dumps({'registered':True,'parents':len(parents),'pending':0}),flush=True)


def run(work):
    import psutil
    s.check(work)
    frozen=s.s.read(work/'tail-birth-frozen.json')
    for rel,h in frozen['sources'].items():assert s.s.sha(s.ROOT/rel)==h
    assert not any((work/n).exists() for n in ('in-flight.json','STOP','tail-birth-summary.json'))
    rows=[];start=time.monotonic()
    with s.s.base.worker_lock(work),s.pre.Guard(work) as guard:
        host={'pid':os.getpid(),'created':psutil.Process().create_time(),'command':s.sys.argv}
        s.s.write(work/'tail-birth-host.json',host)
        for key,parent_hash in frozen['parents'].items():
            if (work/'STOP').exists():return
            assert guard.thread.is_alive() and s.s.base.resource_check(work)['safe']
            out=work/'birth-tails'/key;out.mkdir(parents=True,exist_ok=False)
            s.s.write(work/'in-flight.json',host|{'key':'birth-tails/'+key})
            parent=s.get(work/'cases'/key/'final.rstate.gz');assert parent.digest==parent_hash
            e=s.engine(state=parent);assert e.capture_state().digest==parent_hash
            s.put(out/'initial.rstate.gz',e.capture_state())
            begin=e.time_us;started=time.monotonic();points=[]
            for delay in DELAYS:
                e.advance_to(begin+delay*1000000)
                image=e.capture_state();d=image.to_dict();nodes=e.observation_nodes()
                assert image.digest==e.capture_state().digest
                s.put(out/f'tail-{delay}.rstate.gz',image)
                points.append({'requested_seconds':delay,'actual_seconds':(e.time_us-begin)/1e6,
                               'time_us':e.time_us,'life':e.life,'nodes':nodes,'active':d['active'],
                               'quiet_since_us':d['quiet_since_us'],'transport':d['transport'],'sha256':image.digest})
                if time.monotonic()-started>=300 and not (work/'STOP').exists():
                    s.s.write(work/'STOP',{'reason':'supplementary tail wall budget; pause after complete tail'})
                if e.life=='dead':break
            final=e.capture_state();s.put(out/'final.rstate.gz',final)
            result={'key':key,'parent_sha256':parent_hash,'initial_sha256':parent_hash,
                    'final_sha256':final.digest,'config':final.to_dict()['config'],
                    'points':points,'wall_seconds':time.monotonic()-started,'no_reconfigure':True}
            s.s.write(out/'result.json',result);rows.append(result)
            (work/'in-flight.json').unlink()
            s.s.base.atomic_json(work/'tail-birth-current.json',{'complete':len(rows),'total':8,'last':key})
            size=sum(p.stat().st_size for p in (work/'birth-tails').rglob('*') if p.is_file())
            if (size>frozen['additional_original_cap'] or time.monotonic()-start>600) and not (work/'STOP').exists():
                s.s.write(work/'STOP',{'reason':'supplementary tail complete-boundary budget','bytes':size})
            print(json.dumps({'complete':len(rows),'key':key,'actual_seconds':points[-1]['actual_seconds'],
                              'life':e.life,'remaining_active':len(points[-1]['active'])}),flush=True)
        s.s.write(work/'tail-birth-summary.json',{'stages':8,'wall_seconds':time.monotonic()-start})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'))
    p.add_argument('--work',type=Path,required=True);a=p.parse_args();globals()[a.action](a.work)
