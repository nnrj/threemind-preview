"""R51t1 registered bounded diagnosis; does not resume the paused campaign."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import design
import execute_cause as e
s=e.s
ROOT=e.materials.ROOT
NS=UUID('1b67ff6a-ccfa-43a3-83bc-bec41a93e028')
read=s.base.read
CAP=2*2**30

def native():
 from _threemind_native import _threemind_native as n
 return Path(n.__file__)

def check(work):
 f=read(work/'frozen.json')
 for rel,sha in f['sources'].items():assert s.sha(ROOT/rel)==sha,rel
 assert s.sha(native())==f['native_sha256']
 assert s.sha(work/'cases.json')==f['cases_sha256']
 for rel,sha in f['materials'].items():assert s.sha(work/rel)==sha,rel
 assert read(work/'registration.json')['pending']==0
 return f

def register(work):
 assert not work.exists()
 prior=work.parent/'memory-timescales61-v1'
 done=read(prior/'publication/completion.json')
 assert done['coverage']=='verified' and done['pending']==0 and done['scientific_stop']
 assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>31.125*2**30
 cases=design.cases(read(prior/'cases.json'))
 for c in cases:e.base.resolve_kernel('threemind.continuous-memory/'+c['version']).configuration({'seed':e.materials.SEED,**c['initial_config'],**c['birth_patch'],**c['cause_patch'],**c['patch']})
 work.mkdir();materials={}
 for key in sorted({c['material_key'] for c in cases}):
  p=prior/'materials'/key/'frames.jsonl';dst=work/'materials'/key/'frames.jsonl'
  dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
  assert s.sha(p)==s.sha(dst)
  materials[dst.relative_to(work).as_posix()]=s.sha(dst)
 s.base.original(work/'cases.json',cases)
 paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
 paths += [HERE.parent/'memory_timescales'/n for n in ('materials_timescales.py','measurement_timescales.py','execute_timescales.py')]
 paths += list((ROOT/'src/threemind_kernels').glob('*.py'))+[Path(s.__file__),Path(s.base.__file__)]
 sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
 s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'cases_sha256':s.sha(work/'cases.json'),
  'native_sha256':s.sha(native()),'prior_completion_sha256':s.sha(prior/'publication/completion.json'),
  'blocks':2,'stages':len(cases),'originals_cap_bytes':CAP,'current_authorization':'2026-11-14 explicit cause investigation after R51t stop'})
 for rel in sources:
  dst=work/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
 s.base.load_env()
 import httpx
 with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
  rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
  rec.register({'source_key':'r51t1:persistent-cause:20261114:v1','title':'R51t1：持续活动与前缀区分的原因定位',
   'classification':'formal','execution_status':'running','executor':'ai',
   'kernels':['threemind.continuous-memory/'+v for v in ('2','3.1','5.1','5.3','6.1')],
   'protocol':(HERE/'protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
   'required_roles':['protocol','report','note','original'],'metadata':{'material_blocks':2,'stages':384,'campaign_paused':True}},request_id=uuid5(NS,'register'))
  for lang in ('zh','en'):
   rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
    'expected_revision':0,'kind':'protocol','title':'R51t1 protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
  rec.synchronize(strict=True)
  result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
  s.base.original(work/'registration.json',result)
 print(json.dumps(result),flush=True)

def execute(c,folder,work,source=None,mode='observed',calibration=False):
 initial=e.base.image(source/'final.tmind') if source else None
 observer=e.unpacked(source/'observer.json.xz') if source else None
 return e.execute(c,folder,work/'materials',initial,observer,mode=mode,calibration=calibration)

def apparatus(work):
 check(work);assert not any((work/x).exists() for x in ('apparatus','apparatus.json','in-flight.json','STOP'))
 import psutil
 cs={c['key']:c for c in read(work/'cases.json')};checks=[]
 with s.base.worker_lock(work),s.base.Guard(work) as guard:
  s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
  for variant in ('v2','v61'):
   keys=[variant+'/retention/s0/011/paired/train',variant+'/readout/s0/011/paired/d300/wait',variant+'/sustain/s0/unchanged',variant+'/short/train-0',variant+'/history/s0/101/d1/AB']
   for key in keys:
    c=cs[key];src=work/'apparatus/main'/c['parent'] if c['parent'] else None
    r,state,observer=execute(c,work/'apparatus/main'/key,work,src,calibration=True)
    if c['kind']=='probe':
     hashes={'observed':state.digest}
     for mode in ('plain','restored','paused'):
      _,other,ob=execute(c,work/'apparatus'/mode/key,work,src,mode=mode,calibration=True)
      assert ob==observer
      hashes[mode]=other.digest
     assert len(set(hashes.values()))==1
     checks.append({'key':key,'hashes':hashes,'observers_equal':True})
    print('apparatus',key,flush=True)
    assert not (work/'STOP').exists()
  s.base.original(work/'apparatus.json',{'passed':True,'calibration_seed':9291199,'channel_xor':0x20000000,'checks':checks})
  (work/'in-flight.json').unlink()
 shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
 print(json.dumps({'passed':True,'checks':len(checks)}),flush=True)

def run(work):
 check(work);assert read(work/'apparatus.json')['passed']
 assert not any((work/n).exists() for n in ('summary.json','in-flight.json','STOP'))
 import psutil
 cases=read(work/'cases.json');start=time.monotonic();count=0
 with s.base.worker_lock(work),s.base.Guard(work) as guard:
  s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
  for c in cases:
   if (work/'STOP').exists():break
   folder=work/'cases'/c['key']
   if folder.exists():
    r=read(folder/'result.json');assert r['status']=='complete' and e.base.image(folder/'final.tmind').digest==r['final_sha256'];count+=1;continue
   assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
   s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
   source=work/'cases'/c['parent'] if c['parent'] else None
   r,_,_=execute(c,folder,work,source)
   count+=1
   s.base.atomic_json(work/'current.json',{'complete':count,'total':len(cases),'last':c['key'],'elapsed_seconds':time.monotonic()-start})
   (work/'in-flight.json').unlink()
   assert e.support.allocated(work)<CAP,'originals budget exceeded at complete boundary'
   print(json.dumps({'complete':count,'key':c['key'],'seconds':r['wall_seconds']}),flush=True)
   gc.collect()
  if count==len(cases):s.base.original(work/'summary.json',{'complete':count,'wall_seconds':time.monotonic()-start})
 print(json.dumps({'complete':count,'total':len(cases)}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run','check'));p.add_argument('--work',type=Path,required=True)
 a=p.parse_args();globals()[a.action](a.work)
