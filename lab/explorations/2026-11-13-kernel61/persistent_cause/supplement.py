"""Bounded registered identity correction and retention-system contrasts."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import investigate as h
s=h.s;e=h.e
FACTORS=[('v1','1',{}),('v31-legacy-edges','3.1',{'consolidation_mode':'legacy-stability'}),
 ('v31-legacy-all','3.1',{'consolidation_mode':'legacy-stability','node_retention_mode':'manual'}),
 ('v51-legacy-edges','5.1',{'consolidation_mode':'legacy-stability'})]

def check(work):
 h.check(work);f=h.read(work/'supplement-frozen.json')
 for rel,digest in f['sources'].items():assert s.sha(h.ROOT/rel)==digest
 assert s.sha(work/'supplement-cases.json')==f['cases_sha256']
 assert h.read(work/'supplement-registration.json')['pending']==0

def register(work):
 h.check(work);assert not (work/'supplement-frozen.json').exists()
 base=[c for c in h.read(work/'cases.json') if c['variant']=='v2'];cases=[]
 for name,version,patch in FACTORS:
  for c in base:
   d=dict(c,key=name+'/'+c['material_key'],variant=name,version=version,birth_patch=patch,
     parent=(name+'/'+c['parent'].split('/',1)[1]) if c['parent'] else None)
   e.base.resolve_kernel('threemind.continuous-memory/'+version).configuration({'seed':e.materials.SEED,**d['initial_config'],**patch})
   cases.append(d)
 assert len(cases)==80
 proof=[]
 for c in h.read(work.parent/'memory-timescales61-v1/cases.json'):
  p=e.materials.OLD/'cases'/c['key']/'result.json';v=h.read(p)
  assert v['kernel']=='threemind.continuous-memory/1'
  proof.append({'key':c['key'],'kernel':v['kernel'],'sha256':s.sha(p)})
 s.base.original(work/'historical-identity-proof.json',{'rows':proof,'count':len(proof),'kernel':'threemind.continuous-memory/1'})
 s.base.original(work/'supplement-cases.json',cases)
 files=[HERE/'supplement.py',HERE/'analyze_v2.py',HERE/'identity-correction.zh.md',HERE/'identity-correction.en.md']
 sources={p.relative_to(h.ROOT).as_posix():s.sha(p) for p in files}
 s.base.original(work/'supplement-frozen.json',{'sources':sources,'cases_sha256':s.sha(work/'supplement-cases.json'),'stages':80,'registered_after_initial_version_observations':True})
 for p in files:
  dest=work/'supplement-source'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest)
 s.base.load_env();import httpx
 with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
  rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client);rec.resume_recording()
  for lang in ('zh','en'):
   rec.text({'identity':str(uuid5(h.NS,'supplement-document-'+lang)),'request_id':str(uuid5(h.NS,'supplement-'+lang)),
    'expected_revision':0,'kind':'protocol','title':'R51t1 historical identity correction and supplementary contrasts '+lang,
    'markdown':(HERE/f'identity-correction.{lang}.md').read_text('utf8')})
  rec.append('correction','r51t1:historical-identity',{'historical_kernel':'threemind.continuous-memory/1',
   'historical_files':592,'supplemental_stages':80,'cases_sha256':s.sha(work/'supplement-cases.json'),
   'scientific_thresholds_unchanged':True,'initial_comparisons_preserved':384},request_id=uuid5(h.NS,'supplement-cases'))
  rec.synchronize(strict=True)
  result={'pending':rec.status['pending'],'record':rec.experiment,'registered_before_supplement':True}
  s.base.original(work/'supplement-registration.json',result)
 print(json.dumps(result),flush=True)

def apparatus(work):
 check(work);assert h.read(work/'summary.json')['complete']==384
 assert not any((work/n).exists() for n in ('in-flight.json','STOP','supplement-apparatus.json'))
 cs={c['key']:c for c in h.read(work/'supplement-cases.json')};checks=[]
 import psutil
 shutil.copyfile(work/'resource-summary.json',work/'primary-resources.json')
 with s.base.worker_lock(work),s.base.Guard(work):
  s.base.original(work/'in-flight.json',{'phase':'supplement-apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
  for key in ('v1/retention/s0/011/paired/train','v1/readout/s0/011/paired/d300/wait','v1/sustain/s0/unchanged','v1/short/train-0','v1/history/s0/101/d1/AB'):
   c=cs[key];src=work/'supplement-apparatus/main'/c['parent'] if c['parent'] else None
   _,state,observer=h.execute(c,work/'supplement-apparatus/main'/key,work,src,calibration=True)
   if c['kind']=='probe':
    hashes={'observed':state.digest}
    for mode in ('plain','restored'):
     _,other,ob=h.execute(c,work/'supplement-apparatus'/mode/key,work,src,mode=mode,calibration=True)
     assert ob==observer;hashes[mode]=other.digest
    assert len(set(hashes.values()))==1;checks.append({'key':key,'hashes':hashes})
   print('supplement apparatus',key,flush=True)
  s.base.original(work/'supplement-apparatus.json',{'passed':True,'checks':checks});(work/'in-flight.json').unlink()
 shutil.copyfile(work/'resource-summary.json',work/'supplement-apparatus-resources.json')

def run(work):
 check(work);assert h.read(work/'supplement-apparatus.json')['passed']
 assert not any((work/n).exists() for n in ('in-flight.json','STOP','supplement-summary.json'))
 import psutil
 cases=h.read(work/'supplement-cases.json');began=time.monotonic();completed=0
 with s.base.worker_lock(work),s.base.Guard(work) as guard:
  s.base.atomic_json(work/'supplement-host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
  for c in cases:
   if (work/'STOP').exists():break
   folder=work/'cases'/c['key'];assert not folder.exists()
   assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
   s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
   src=work/'cases'/c['parent'] if c['parent'] else None
   r,_,_=h.execute(c,folder,work,src);completed+=1
   s.base.atomic_json(work/'supplement-current.json',{'complete':completed,'total':80,'last':c['key']})
   (work/'in-flight.json').unlink()
   assert e.support.allocated(work)<h.CAP
   print(json.dumps({'supplement':completed,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
  if completed==80:s.base.original(work/'supplement-summary.json',{'complete':80,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run'));p.add_argument('--work',type=Path,required=True)
 a=p.parse_args();globals()[a.action](a.work)
