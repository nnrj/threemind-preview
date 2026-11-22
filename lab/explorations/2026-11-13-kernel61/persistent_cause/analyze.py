"""Read-only state, input and arithmetic audit for R51t1."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import investigate as host
e=host.e;s=host.s
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m

def analyze(work):
 host.check(work)
 assert host.read(work/'summary.json')['complete']==384 and not (work/'in-flight.json').exists()
 cases=host.read(work/'cases.json');records={};rows=[];waits={};baseline=[];nstate=0;ninput=0
 prior=work.parent/'memory-timescales61-v1'
 for i,c in enumerate(cases):
  folder=work/'cases'/c['key'];r=host.read(folder/'result.json')
  assert r['status']=='complete' and r['kernel']=='threemind.continuous-memory/'+c['version']
  assert r['begin_us']==c['begin_us'] and r['end_us']==c['end_us'] and r['life']=='active'
  images={n:e.base.image(folder/(n+'.tmind')) for n in ('initial','intervened','final')}
  for n,im in images.items():
   assert im.digest==r[n+'_sha256'];assert im.to_dict()['dynamics']==r['kernel'];nstate+=1
  if c['parent']:
   assert records[c['parent']]['final_sha256']==r['parent_sha256']==r['initial_sha256']
   assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(work/'cases'/c['parent']/'observer.json.xz')
  before=images['initial'].to_dict();changed=images['intervened'].to_dict();final=images['final'].to_dict()
  patch=c['patch']|c['cause_patch']
  assert changed['config']==before['config']|patch and final['config']==changed['config']
  assert int(before['time_us'])==int(changed['time_us'])==c['begin_us'] and int(final['time_us'])==c['end_us']
  intervention=host.read(folder/'intervention.json')
  assert intervention['advanced_us']==0 and intervention['changes']==e.support.x.differences(before,changed)
  inputs=e.unpacked(folder/'inputs.json.xz');expected=e.material_frames(c,work/'materials')
  assert inputs==expected
  deliveries=e.unpacked(folder/'delivered.json.xz')
  assert len(inputs)==len(deliveries)==r['inputs'];ninput+=len(inputs)
  scheduled=e.unpacked(folder/'scheduled.json.xz');assert len(scheduled)==len(inputs)
  by_event={}
  for a,b in zip(inputs,scheduled):
   assert a['enqueue_us']==b['enqueue_us'] and a['source']==b['receipt']['source']
   assert int(a['stimulus']['time_us'])==int(b['receipt']['scheduled_time_us'])
   by_event[b['receipt']['core_event_id']]=b['enqueue_us']
  norm=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
  assert Counter(norm({k:x[k] for k in ('stimulus','source','enqueue_us')}) for x in inputs)==Counter(
    norm({'stimulus':x['stimulus'],'source':x['source'],'enqueue_us':by_event[x['core_event_id']]}) for x in deliveries)
  assert all(x['status']=='delivered' and not x.get('labels') and x['stimulus']['time_us']==x['scheduled_time_us']==x['delivered_time_us'] for x in deliveries)
  with zipfile.ZipFile(folder/'milestones.zip') as archive:
   assert set(archive.namelist())=={x+'.tmind' for x in r['snapshots']}
   for name,digest in r['snapshots'].items():
    im=e.base.ArtifactCodec.decode(archive.read(name+'.tmind'))
    assert im.digest==digest and im.to_dict()['dynamics']==r['kernel'];nstate+=1
  observer=e.unpacked(folder/'observer.json.xz')
  assert observer['input_bus']['pending']=={}
  trajectory=e.unpacked(folder/'trajectory.json.xz');points=trajectory['points']
  if c['kind']=='probe':rows.append(m.process(c,points))
  if c['kind']=='readout_wait':
   vals=[(p['time_us']-c['begin_us'],max((n['activation'] for n in p['nodes']),default=0.)) for p in points]
   waits[c['key']]={'last_positive_us':max((t for t,v in vals if v>0),default=None),'end':vals[-1][1],
      'checkpoints':{str(seconds):next((v for t,v in vals if t==seconds*1000000),None) for seconds in (1,30,60,300)}}
  if c['variant']=='v61':
   old=host.read(prior/'cases'/c['material_key']/'result.json')
   assert r['final_sha256']==old['final_sha256'],('6.1 reference changed',c['key'])
   baseline.append({'key':c['key'],'digest':r['final_sha256']})
  records[c['key']]=r
  if (i+1)%32==0:print('audited',i+1,'/384',flush=True)
 index={r['key']:r for r in rows};variants=[]
 for name in dict.fromkeys(c['variant'] for c in cases):
  blocks=[]
  for b in (0,1):
   sustained={a:index[f'{name}/sustain/s{b}/{a}']['task_activity'] for a in host.design.ARMS}
   intact=sustained['unchanged']
   prefix=[index[f'{name}/history/s{b}/101/d1/{cue}'] for cue in ('AB','DB')]
   blocks.append({'block':b,'sustained':sustained,'sustained_passed':intact['first']>m.EPS and intact['minimum']>m.EPS,
    'prefix_margins':[x['signed_peak'] for x in prefix],'prefix_areas':[x['signed_area'] for x in prefix],
    'prefix_passed':all(x['signed_peak']>m.EPS for x in prefix),
    'wait':waits[f'{name}/readout/s{b}/011/paired/d300/wait']})
  variants.append({'variant':name,'blocks':blocks,'sustained_blocks':sum(b['sustained_passed'] for b in blocks),
   'prefix_blocks':sum(b['prefix_passed'] for b in blocks)})
 old_check=[]
 for b in (0,1):
  for cue in ('AB','DB'):
   key=f'history/s{b}/101/d1/{cue}';old=host.read(e.materials.OLD/'cases'/key/'result.json')['extra']['post_cue']
   row=index['v2/'+key];target=row['target'];other=row['other']
   old_value=old[target]['peak']-old[other]['peak']
   old_check.append({'key':key,'historical':old_value,'replayed':row['signed_peak'],'absolute_error':abs(old_value-row['signed_peak'])})
 assert all(v['absolute_error']<1e-9 for v in old_check),'historical prefix reproduction failed'
 assert next(v for v in variants if v['variant']=='v2')['sustained_blocks']==2,'historical sustained baseline absent'
 assert next(v for v in variants if v['variant']=='v61')['sustained_blocks']==0
 assert next(v for v in variants if v['variant']=='v61')['prefix_blocks']==0
 result={'variants':variants,'process':rows,'old_prefix_replay':old_check,'source_blocks':2,'stages':384,
  'scientific_stop':True,'campaign_decision':'remain paused for author review; diagnostic batch does not change defaults',
  'maximum_arithmetic_error':max(r['arithmetic_error'] for r in rows)}
 s.base.original(work/'analysis.json',result)
 s.base.original(work/'audit.json',{'passed':True,'scientific_stop':True,'stages':384,'complete_states':nstate,'inputs':ninput,
  'exact_61_references':baseline,'historical_prefix_replay':old_check,'maximum_arithmetic_error':result['maximum_arithmetic_error'],
  'apparatus':host.read(work/'apparatus.json')})
 print('analysis complete',[(v['variant'],v['sustained_blocks'],v['prefix_blocks']) for v in variants],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();analyze(a.work)

