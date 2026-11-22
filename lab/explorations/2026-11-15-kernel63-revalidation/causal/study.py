"""Eight-origin M1 replication on explicit 6.3, with complete causal copies."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'src'),str(HERE.parent),str(ROOT/'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
import pilot_m1 as old
import pilot_m2 as old_base
from threemind_core import StateImage,Stimulus
from threemind_kernels.registry import resolve_kernel

KERNEL='threemind.continuous-memory/6.3'
PROJECT='d0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS=UUID('1a0b9c28-e18e-50d3-b4c0-47c7b63b6438')
ARMS=old.ARMS


def read(path):return json.loads(Path(path).read_bytes())
def load(path):return json.loads(gzip.decompress(Path(path).read_bytes()))


class Subject:
    def __init__(self,case,saved=None):
        self.case=case
        if saved is None:
            self.channels,self.rng=old_base.mapping(case['seed'])
            self.events=old_base.schedule(case,self.channels);self.cursor=0;self.rows=[];self.stats=old.new_stats()
            self.engine=resolve_kernel(KERNEL).create({'seed':case['seed'],'energy_seed':case['seed']^0x1634AB},backend='native')
        else:
            assert saved['case']==case and saved['kernel']==KERNEL
            self.channels,self.rng=saved['mappings'],saved['random_state']
            self.events,self.cursor=saved['schedule'],saved['cursor']
            self.rows,self.stats=copy.deepcopy(saved['rows']),copy.deepcopy(saved['stats'])
            self.engine=resolve_kernel(KERNEL).create(state=StateImage.from_dict(saved['core']),backend='native')
            assert s.base.digest(self.save())==s.base.digest(saved)

    def save(self):
        return {'kernel':KERNEL,'case':self.case,'core':self.engine.capture_state().to_dict(),
                'mappings':self.channels,'random_state':self.rng,'schedule':self.events,'cursor':self.cursor,
                'rows':self.rows,'stats':self.stats,'readout':{'rule':'fixed A-minus-B','trainable':False},
                'optimizer':None,'body':None,'actuator':None}

    def advance(self,target,preprobe=False):
        first=self.engine.time_us if self.cursor==0 else self.engine.time_us+50000
        # Probe held at 18 seconds must be delivered at the same timestamp in the copy.
        if self.cursor<len(self.events) and int(self.events[self.cursor]['stimulus']['time_us'])==self.engine.time_us:
            first=self.engine.time_us
        for t in range(first,target+1,50000):
            while self.cursor<len(self.events) and int(self.events[self.cursor]['stimulus']['time_us'])<=t:
                row=self.events[self.cursor]
                if preprobe and row['kind']=='probe':break
                self.engine.inject(Stimulus.from_dict(row['stimulus']));self.cursor+=1
            self.engine.advance_to(t)
            before=self.engine.capture_state().digest
            nodes=self.engine.observation_nodes()
            assert before==self.engine.capture_state().digest
            by={n['channel']:n for n in nodes}
            if 1000000<=t<=17000000:
                self.stats['n']+=1
                for symbol,channel in self.channels.items():self.stats['sums'][symbol]+=by.get(channel,{}).get('activation',0.)
            self.rows.append({'time_us':t,'nodes':nodes,'projection':{f:[by.get(self.channels[k],{}).get(f,0.) for k in 'ABZW'] for f in ('activation','inhibition','direct','associative')}})
            if self.engine.life=='dead':break


def mask(subject,selection,arm):
    before=subject.save();edges=[r['edge'] for r in selection['groups']['matched' if arm=='matched' else 'target']]
    if arm!='intact':subject.engine.intervene(edges=[] if arm=='sham' else edges,action='silence')
    masked=subject.save()
    changed=set(old.differences(before,masked))
    assert changed<={'core.silenced_edges'}
    if arm=='restored':subject.engine.intervene(edges=edges,action='restore')
    after=subject.save()
    if arm=='restored':assert s.base.digest(before)==s.base.digest(after)
    return {'arm':arm,'edges':edges,'before':s.base.digest(before),'masked':s.base.digest(masked),'after':s.base.digest(after),'changed_fields':sorted(changed)}


def register(work):
    assert not work.exists()
    assert read(work.parent/'stimulus-63-rerun-v1/publication/completion.json')['pending']==0
    s.base.resource_check(work.parent);work.mkdir()
    import _threemind_native._threemind_native as native
    sources=[Path(__file__),HERE/'protocol.zh.md',HERE/'protocol.en.md',HERE/'analyze.py',HERE/'verify.py',HERE.parent/'support.py',HERE.parent/'allocation.py',Path(old.__file__),Path(old_base.__file__)]
    production=read(work.parent/'stimulus-63-rerun-v1/frozen.json')
    manifest={'sources':{p.relative_to(ROOT).as_posix():s.sha(p) for p in sources},
              'native_sha256':s.sha(native.__file__),'kernel':KERNEL,'parents':old.parents(),
              'production_sources':{k:v for k,v in production['sources'].items() if k.startswith(('src/', 'crates/'))}}
    s.base.original(work/'frozen.json',manifest)
    for rel in manifest['sources'] | manifest['production_sources']:
        dest=work/'frozen-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/rel).read_bytes())
    case=old.parents()[0]|{'id':'instrument','origin':'instrument','seed':817001}
    subject=Subject(case);subject.advance(18000000,preprobe=True)
    original=subject.save();selection=old.select_edges(subject.engine.graph(),subject.channels,0,subject.stats)
    arms={};instrument_finals={}
    for arm in ARMS:
        child=Subject(case,original);arms[arm]=mask(child,selection,arm)
        child.advance(20000000);instrument_finals[arm]=s.base.digest(child.save())
    assert instrument_finals['intact']==instrument_finals['sham']==instrument_finals['restored']
    assert instrument_finals['target']!=instrument_finals['intact']
    s.base.original(work/'instrument-parent.json.gz',original,compressed=True)
    s.base.original(work/'instrument-check.json',{'passed':True,'scientific_origins':0,'selection':selection,'arms':arms,'final_digests':instrument_finals})
    import os,httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,PROJECT,client=client)
        rec.register({'source_key':'r63b:causal:6.3:20261115:v1','title':'R63b：6.3经历相关连接的因果作用','classification':'formal','execution_status':'running','executor':'ai','kernels':[KERNEL],
                      'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
                      'required_roles':['protocol','report','note','original'],'metadata':{'independent_origins':8,'teaching_references':16,'causal_copies':80,'historical_reference':'M1 silence pilot','instrument_excluded':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),'expected_revision':0,'kind':'protocol','title':'R63b protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result);print(json.dumps(result))


def run(work):
    import psutil
    assert read(work/'registration.json')['pending']==0
    assert not (work/'summary.json').exists()
    frozen=read(work/'frozen.json')
    for rel,h in frozen['sources'].items()|frozen['production_sources'].items():assert s.sha(ROOT/rel)==h,rel
    import _threemind_native._threemind_native as native
    assert s.sha(native.__file__)==frozen['native_sha256']
    with s.base.worker_lock(work),s.base.Guard(work):
        assert not (work/'in-flight.json').exists(),'Preserve orphaned in-flight state'
        start=time.monotonic();completed=[]
        for case in frozen['parents']:
            folder=work/'parents'/case['id']
            if not (folder/'parent.json.gz').exists():
                assert not (work/'STOP').exists();s.base.resource_check(work)
                s.base.original(work/'in-flight.json',{'kind':'teaching','case':case['id'],'pid':psutil.Process().pid,'created':psutil.Process().create_time()})
                subject=Subject(case);subject.advance(9000000)
                s.base.original(folder/'boundary-9s.json.gz',subject.save(),compressed=True)
                subject.advance(18000000,preprobe=True)
                parent=subject.save();selection=old.select_edges(subject.engine.graph(),subject.channels,case['history'],subject.stats)
                s.base.original(folder/'selection.json',selection);s.base.original(folder/'parent.json.gz',parent,compressed=True)
                (work/'in-flight.json').unlink()
            parent=load(folder/'parent.json.gz');selection=read(folder/'selection.json')
            for arm in ARMS:
                out=folder/arm
                if not (out/'result.json').exists():
                    assert not (work/'STOP').exists();s.base.resource_check(work)
                    s.base.original(work/'in-flight.json',{'kind':'causal-copy','case':case['id'],'arm':arm,'pid':psutil.Process().pid,'created':psutil.Process().create_time()})
                    child=Subject(case,parent);intervention=mask(child,selection,arm)
                    s.base.original(out/'initial.json.gz',child.save(),compressed=True)
                    child.advance(20000000);final=child.save()
                    s.base.original(out/'final.json.gz',final,compressed=True)
                    rows=[r for r in child.rows if 18100000<=r['time_us']<=18300000]
                    response=sum(r['projection']['activation'][0]-r['projection']['activation'][1] for r in rows)/len(rows) if rows else None
                    result={'case':case,'arm':arm,'selection_valid':selection['matching_passed'],'primary_response':response,'intervention':intervention,'final_digest':s.base.digest(final),'clock_us':child.engine.time_us,'life':child.engine.life}
                    s.base.original(out/'result.json',result);(work/'in-flight.json').unlink()
                completed.append(case['id']+'/'+arm)
                s.base.atomic_json(work/'current.json',{'completed_copies':len(completed),'total_copies':80,'last':completed[-1]})
                print(completed[-1],flush=True)
            if time.monotonic()-start>7200 or sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>128*2**20:
                s.base.original(work/'STOP',{'reason':'registered time/evidence budget','complete_boundary':case['id']});raise RuntimeError('Complete-boundary stop')
        s.base.original(work/'summary.json',{'status':'awaiting-analysis','origins':8,'parents':16,'causal_copies':80,'wall_seconds':time.monotonic()-start})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run']);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();(register if a.action=='register' else run)(a.work.resolve())
