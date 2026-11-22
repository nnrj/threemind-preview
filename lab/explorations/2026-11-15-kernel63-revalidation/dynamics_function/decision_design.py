"""R63t4 bounded materials; no engine construction."""
from itertools import product
import random

SEEDS=(941101,941102,941103,941104)
FIELDS=('activation','inhibition','direct','associative')
TOKENS={'A':2932,'B':4786,'C':6969,'D':2064,'E':1925,'X':201311,'keep':201312}
PROFILES={'reference':{},'short-inhibition':{'inhibition_tau':0.0580338705786432},
    'prefix-candidate':{'novelty_mode':'immediate','inhibitory_learning_enabled':False},
    'no-inhibition':{'inhibition':False}}

def mapping(seed):
    mask=(seed*2654435761)&0xffffffff
    return {k:v^mask for k,v in TOKENS.items()},mask

def table():
    rows=[]
    for block,seed in enumerate(SEEDS):
        for task,swap,profile in product(('pair','prefix'),(0,1),PROFILES):
            tests=[{'cue':cue,'delay':delay,'distractor':False} for delay in (.5,3.,30.,60.) for cue in ('A','D')]
            tests += [{'cue':cue,'delay':delay,'distractor':True} for delay in (3.,30.) for cue in ('A','D')]
            tests += [{'cue':None,'delay':30.,'distractor':False} for _ in range(2)]
            random.Random(seed+(0 if task=='pair' else 10000)).shuffle(tests)
            dev=[{'cue':cue,'delay':delay,'distractor':False} for delay in (.5,1.) for cue in ('A','D')]
            rows.append({'key':f'b{block}/{task}/s{swap}/{profile}','block':block,'seed':seed,'task':task,'swap':swap,
                'profile':profile,'patch':PROFILES[profile],'development':dev,'tests':tests})
    assert len(rows)==64
    return rows

def expected(c,cue):
    if cue is None:return 'WAIT'
    return ('C','E')[int(cue=='D')^c['swap']]

def lesson(c,cue,start,strength=1.):
    target=expected(c,cue)
    if c['task']=='pair':return [(start,(cue,target),strength)]
    return [(start,(cue,),strength),(start+1000000,(cue,'B'),strength),(start+2000000,('B',target),strength)]

def review(c):
    t=0;out=[]
    for gap in (1,3,9):
        t+=int(gap*1e6)
        for cue in ('A','D'):
            out+=lesson(c,cue,t);t+=3000000
    return out,t+1000000

def correction(c,cue,wrong):
    # Same phase length for correct and incorrect answers; prior correct material is reviewed.
    out=lesson(c,cue,1000000)
    if wrong:
        for start,strength in ((4000000,1.),(8000000,1.),(14000000,.9),(23000000,.9)):
            out+=lesson(c,cue,start,strength)
    return out,27000000

def question(c,q):
    out=[];cue_time=2000000
    if q['cue'] is not None:
        out.append((cue_time,(q['cue'],),.5))
        if c['task']=='prefix':out.append((cue_time+1000000,('B',),.5))
    origin=cue_time+(1000000 if c['task']=='prefix' and q['cue'] is not None else 0)
    if q['distractor']:out.append((origin+int(q['delay']*500000),('X',),.3))
    return out,origin+int(q['delay']*1e6),origin
