"""Bounded, preregistered R51t1 factors; no kernel construction."""
from copy import deepcopy

VARIANTS=[(f'v{v.replace(".","")}',v,{}) for v in ('2','3.1','5.1','5.3','6.1')]+[
 ('v31-no-fatigue','3.1',{'strong_fatigue_enabled':False}),
 ('signal004','6.1',{'signal_threshold':.004}),
 ('signal-off','6.1',{'signal_threshold_enabled':False}),
 ('senders-zero','6.1',{'activation_send_threshold':0.,'inhibition_send_threshold':0.}),
 ('no-fatigue','6.1',{'strong_fatigue_enabled':False}),
 ('no-inhibition','6.1',{'inhibition':False}),
 ('no-inhibitory-learning','6.1',{'inhibitory_learning_enabled':False}),
 ('no-fast','6.1',{'fast_enabled':False}),
 ('exponential','6.1',{'decay_curve':'exponential'}),
 ('no-context','6.1',{'context_mix':0.}),
 ('signal004-no-fatigue','6.1',{'signal_threshold':.004,'strong_fatigue_enabled':False}),
]
POST=('signal004','no-fatigue','no-inhibition','no-fast')
ARMS=('unchanged','depletion-on','facilitation-off','both','consolidation-off')

def cases(historical):
 index={c['key']:c for c in historical};out=[]
 for variant,version,patch in VARIANTS+[(f'post-{n}',v,p) for n,v,p in VARIANTS if n in POST]:
  post=variant.startswith('post-')
  for block in (0,1):
   keys=[f'retention/s{block}/011/paired/train',f'readout/s{block}/011/paired/d300/wait']
   keys += [f'sustain/s{block}/{a}' for a in ARMS]
   keys += [f'short/train-{block}',f'history/s{block}/101/d1/AB',f'history/s{block}/101/d1/DB']
   for key in keys:
    c=deepcopy(index[key])
    if post and c['parent'] is None:continue
    old_parent=c['parent'];parent_variant='v61' if post and old_parent in (keys[0],keys[7]) else variant
    c.update(material_key=key,variant=variant,version=version,birth_patch={} if post else patch,
             key=variant+'/'+key,parent=(parent_variant+'/'+old_parent) if old_parent else None,
             cause_patch=patch if post and parent_variant=='v61' else {},milestones=[])
    c['scope']='task'
    out.append(c)
 assert len(out)==384 and len({c['key'] for c in out})==384
 seen=set()
 for c in out:
  assert c['parent'] is None or c['parent'] in seen,c['key']
  seen.add(c['key'])
 return out
