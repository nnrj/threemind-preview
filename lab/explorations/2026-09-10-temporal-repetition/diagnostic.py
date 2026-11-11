"""Four predeclared continuous observations, including after the reader closes."""
import json
import time
from dataclasses import asdict
from uuid import uuid4

import psutil
from run import (HERE,WORK,META,Database,Settings,LOCAL_USER,notebooks,encoded,write_new,sha,
                 create_engine,TextSensor,SENSOR,READER,ReadoutSession,SESSION_VERSION)
from threemind_runtime.source_policies import SourcePolicies

def run():
    meta=json.loads(META.read_bytes())
    resultpath=WORK/'diagnostic-continuation.json'
    if resultpath.exists():raise RuntimeError('diagnostic evidence exists')
    sources=[json.loads(p.read_bytes()) for p in WORK.glob('seed-*-results.json')]
    if sum(s['elapsed_s'] for s in sources)>1680:raise RuntimeError('insufficient remaining compute budget')
    quota=HERE/'quota-monitor.json'
    if quota.exists() and json.loads(quota.read_bytes())['used_percent']>=90:raise RuntimeError('quota reserve')
    source=next(s for phase in sources for s in phase['rows'] if s['seed']==41701 and s['arm']=='normal' and s['stage']=='final')
    db=Database(Settings.from_env().database_url)
    try:
        note=notebooks.save_note(db,meta['project_id'],LOCAL_USER,str(uuid4()),dict(operation_id=str(uuid4()),
            expected_revision=0,kind='note',collection_id=meta['notebook_id'],
            title='补充观察设计：提前结束窗口之后继续观察12秒',
            body={'format':'markdown','text':(HERE/'diagnostic-plan.md').read_text(encoding='utf-8')}))
        cp,image=db.load_checkpoint(meta['project_id'],source['run_id'],source['checkpoint_id'])
        assert image.digest==source['source_hash']
        context=cp['context'];started=time.monotonic();rows=[]
        for cue in ['甲','Z的爷爷是谁？']:
          for dose in [1.0,0.0]:
            e=create_engine(state=image);records=[]
            session=ReadoutSession(e,record=records.append,
              state={'schema':SESSION_VERSION,'session_id':context['readouts']['run_id'],
                     'input_bus':context['input_bus'],'readouts':context['readouts']},
              config={'structural_readout':{'enabled':False},'temporal_readout':asdict(READER)},
              policies=SourcePolicies(**context['protocol']['source_policies']))
            at=e.time_us;env=str(uuid4());session.schedule(TextSensor(41701,SENSOR).frames(cue,dose),envelope_id=env)
            curve=[]
            for dt in range(0,12_000_001,20_000):
                if time.monotonic()-started>120:raise TimeoutError('diagnostic wall limit')
                if psutil.Process().memory_info().rss>2*1024**3 or psutil.virtual_memory().available<3*1024**3:
                    raise MemoryError('diagnostic memory limit')
                session.advance_to(at+dt)
                curve.append(dict(time_us=str(e.time_us),relative_us=dt,nodes=[{k:n[k] for k in ['id','channel','activation','inhibition','direct','associative']} for n in e.observation_nodes()]))
                if e.life=='dead':break
            original=next(r['payload'] for r in records if r['kind']=='temporal_readout' and r['payload']['envelope_id']==env)
            rows.append(dict(cue=cue,dose=dose,envelope_id=env,original_readout=original,
                             curve=curve,final_hash=e.capture_state().digest,life=e.life))
        assert db.checkpoint_identity(meta['project_id'],source['run_id'],source['checkpoint_id'])['state_hash']==image.digest
        write_new(resultpath,dict(source=source,source_unchanged=True,rows=rows,elapsed_s=time.monotonic()-started,
                  plan_sha256=sha(HERE/'diagnostic-plan.md'),script_sha256=sha(HERE/'diagnostic.py'),
                  protocol_note_id=str(note['id']),scope='continuous observation; original reader classification unchanged'))
        print('Completed four 12-second diagnostic continuations; source unchanged.')
    finally:db.close()

if __name__=='__main__':run()
