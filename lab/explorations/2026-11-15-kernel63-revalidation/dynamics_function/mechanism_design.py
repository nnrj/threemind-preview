"""Frozen finite configuration table; no scientific engine construction."""
from copy import deepcopy
from itertools import product

TAU=0.2321354823145728

def variants():
    persistent=[(f'g{g:g}-t{f:g}',{'inhibition_gain':g,'inhibition_tau':TAU*f})
        for g,f in product((.24,.06,.015),(1.,.5,.25)) if (g,f)!=(.24,1.)]
    for name,patch in [('depletion',{'depletion_enabled':True}),('no-facilitation',{'stp_facilitation_tau_s':0.}),
                       ('both',{'depletion_enabled':True,'stp_facilitation_tau_s':0.})]:
        persistent.append(('resources-'+name,{'inhibition_gain':.06,'inhibition_tau':TAU*.5,**patch}))
    prefix=[]
    for novelty,threshold,context in product(('arrival-window','immediate'),(.0004,.004),(1.,0.)):
        if threshold==.0004 and context==1.:continue
        prefix.append((f'{novelty}-s{threshold:g}-c{context:g}',
                       {'novelty_mode':novelty,'signal_threshold':threshold,'context_mix':context}))
    for name,patch in [('no-inhibitory-learning',{'inhibitory_learning_enabled':False}),
                       ('g006',{'inhibition_gain':.06}),('g0015',{'inhibition_gain':.015}),
                       ('half-inhibition-time',{'inhibition_tau':TAU*.5}),('no-fast',{'fast_enabled':False})]:
        prefix.append(('immediate-'+name,{'novelty_mode':'immediate',**patch}))
    assert len(persistent)==len(prefix)==11
    return persistent,prefix

def cases(old):
    index={c['material_key']:c for c in old if c['variant']=='v63'};out=[]
    persistent,prefix=variants()
    for name,patch in persistent:
        variant='persist-'+name
        for b in (0,1):
            keys=[f'readout/s{b}/011/paired/d300/wait',f'sustain/s{b}/unchanged']
            for i,key in enumerate(keys):
                c=deepcopy(index[key]);c.update(key=variant+'/'+key,variant=variant,
                    parent=('external:v63/retention/s'+str(b)+'/011/paired/train') if i==0 else variant+'/'+keys[0],
                    cause_patch=patch if i==0 else {},birth_patch={},group='persistent',block=b)
                out.append(c)
    for name,patch in prefix:
        variant='prefix-'+name
        for b in (0,1):
            keys=[f'short/train-{b}',f'history/s{b}/101/d1/AB',f'history/s{b}/101/d1/DB']
            for i,key in enumerate(keys):
                c=deepcopy(index[key]);c.update(key=variant+'/'+key,variant=variant,
                    parent=None if i==0 else variant+'/'+keys[0],birth_patch=patch,cause_patch={},group='prefix',block=b)
                if i:c['milestones']=[10000,100000,1000000,1010000,1100000,2000000]
                out.append(c)
    assert len(out)==110 and len({c['key'] for c in out})==110
    return out
