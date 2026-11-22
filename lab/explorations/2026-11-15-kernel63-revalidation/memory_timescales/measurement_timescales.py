"""Frozen process measures and decision rules, independent of Core execution."""
from collections import Counter
from decimal import Decimal, localcontext
import itertools
import math
from statistics import mean

EPS=1e-6
FIELDS=('activation','inhibition','direct','associative')
TOKENS={'A':2932,'B':4786,'C':6969,'D':2064,'E':1925}
BITS=[''.join(map(str,b)) for b in itertools.product((0,1),repeat=3)]


def process(case,points):
    start=case['probe_start_us']
    assert len(points)==1502
    times=[p['time_us']-start for p in points]
    assert times==[0]+list(range(0,15000001,10000))
    beginning=round(case['gap_s']*1e6) if case['cue'] in ('AB','DB','B') else 0
    rows=[(t,p) for t,p in zip(times,points) if t>=beginning]
    measures={};error=0.
    for symbol in 'CE':
        measures[symbol]={}
        for field in FIELDS:
            pairs=[(t,next((n.get(field,0.) for n in p['nodes'] if n['channel']==TOKENS[symbol]),0.)) for t,p in rows]
            peak_t,peak=max(pairs,key=lambda r:r[1])
            area=math.fsum((b[0]-a[0])*(b[1]+a[1])/2e6 for a,b in itertools.pairwise(pairs))
            with localcontext() as ctx:
                ctx.prec=45
                exact=sum(Decimal(b[0]-a[0])*(Decimal(str(a[1]))+Decimal(str(b[1])))/Decimal(2000000) for a,b in itertools.pairwise(pairs))
            error=max(error,abs(float(exact)-area))
            measures[symbol][field]={'peak':peak,'peak_us':peak_t,'area':area,'final':pairs[-1][1],
                'last_positive_us':max((t for t,v in pairs if v>0),default=None)}
    assert error<1e-9
    target='C' if case['cue'] in ('A','AB') else 'E'
    if case['swap']:target='E' if target=='C' else 'C'
    other='E' if target=='C' else 'C'
    amps=[(t,max((n['activation'] for n in p['nodes'] if n['channel'] in TOKENS.values()),default=0.)) for t,p in zip(times,points)]
    return {'key':case['key'],'cue':case['cue'],'swap':case['swap'],'target':target,'other':other,
            'measures':measures,'signed_peak':measures[target]['activation']['peak']-measures[other]['activation']['peak'],
            'signed_area':measures[target]['activation']['area']-measures[other]['activation']['area'],
            'task_activity':{'first':amps[0][1],'end':amps[-1][1],'maximum':max(v for _,v in amps),
                'minimum':min(v for _,v in amps),'last_positive_us':max((t for t,v in amps if v>0),default=None)},
            'arithmetic_error':error}


def contrasts(values):
    output={}
    for width in (1,2,3):
        for axes in itertools.combinations(range(3),width):
            fixed_axes=[i for i in range(3) if i not in axes];strata=[]
            for fixed in itertools.product((0,1),repeat=len(fixed_axes)):
                total=0.
                for varied in itertools.product((0,1),repeat=width):
                    bits=[None]*3
                    for i,v in zip(fixed_axes,fixed):bits[i]=v
                    for i,v in zip(axes,varied):bits[i]=v
                    total+=(-1)**(width-sum(varied))*values[''.join(map(str,bits))]
                strata.append({'fixed':dict(zip(('DFL'[i] for i in fixed_axes),fixed)),'effect':total})
            output[''.join('DFL'[i] for i in axes)]={'mean':mean(r['effect'] for r in strata),'strata':strata}
    return output


def decide(rows):
    index={r['key']:r for r in rows};assert len(index)==510
    retention=[];readout=[];history=[];sustained=[];interactions={}
    for bits,delay in itertools.product(BITS,(1,30,300)):
        cells=[]
        for swap,cue in itertools.product((0,1),('A','D')):
            prefix=f'retention/s{swap}/{bits}'
            a=index[f'{prefix}/paired/d{delay}/{cue}'];b=index[f'{prefix}/balanced/d{delay}/{cue}']
            cells.append({'swap':swap,'cue':cue,'paired':a['signed_peak'],'balanced':b['signed_peak'],
                          'effect':a['signed_peak']-b['signed_peak']})
        retention.append({'bits':bits,'delay_s':delay,'cells':cells,'mean_effect':mean(v['effect'] for v in cells),
                          'positive':sum(v['effect']>EPS for v in cells),'passed':all(v['effect']>EPS and v['paired']>EPS for v in cells)})
    for bits,delay in itertools.product(('001','011','101','111'),(30,300)):
        cells=[]
        for swap,cue in itertools.product((0,1),('A','D')):
            prefix=f'readout/s{swap}/{bits}'
            a=index[f'{prefix}/paired/d{delay}/{cue}'];b=index[f'{prefix}/balanced/d{delay}/{cue}']
            original=index[f'retention/s{swap}/{bits}/paired/d{delay}/{cue}']['signed_peak']
            cells.append({'swap':swap,'cue':cue,'on':original,'off':a['signed_peak'],
                'effect':a['signed_peak']-b['signed_peak'],
                'retained_fraction':a['signed_peak']/original if abs(original)>EPS else None})
        readout.append({'bits':bits,'delay_s':delay,'cells':cells,'passed':all(c['off']>EPS and c['effect']>EPS for c in cells)})
    for bits,delay in itertools.product(('001','101'),(1,3,20)):
        cells=[]
        for swap in (0,1):
            prefix=f'history/s{swap}/{bits}/d{delay}' if delay!=20 else f'short/s{swap}/{bits}/g1'
            values=[index[f'{prefix}/{cue}']['signed_peak'] for cue in ('AB','DB')]
            cells.append({'swap':swap,'values':values,'passed':all(v>EPS for v in values)})
        history.append({'bits':bits,'delay_s':delay,'cells':cells,'passed':all(c['passed'] for c in cells)})
    for swap in (0,1):
        variants={name:index[f'sustain/s{swap}/{name}']['task_activity'] for name in
                  ('unchanged','depletion-on','facilitation-off','both','consolidation-off')}
        persistent=variants['unchanged']['first']>0 and variants['unchanged']['end']>0
        controlled=all(variants[k]['end']==0 for k in ('depletion-on','facilitation-off','both'))
        retained=variants['consolidation-off']['end']>0
        sustained.append({'swap':swap,'variants':variants,'persistent':persistent,'controlled':controlled,
                          'retained_with_L_off':retained,'passed':persistent and controlled and retained})
    for delay in (1,30,300):
        interactions[str(delay)]=contrasts({r['bits']:r['mean_effect'] for r in retention if r['delay_s']==delay})
    default_memory=all(r['passed'] for r in retention if r['bits']=='101' and r['delay_s'] in (30,300))
    stored_memory=all(r['passed'] for r in readout if r['bits']=='101')
    prefix=[r for r in history if r['bits']=='101']
    prefix_preserved=any(r['passed'] for r in prefix)
    sustained_preserved=all(r['passed'] for r in sustained)
    return {'retention':retention,'test_time_L_off':readout,'prefix':history,'sustained':sustained,
            'interactions':interactions,'default_retention_passed':default_memory,
            'stored_memory_passed':stored_memory,'prefix_preserved_or_extended':prefix_preserved,
            'sustained_mechanism_passed':sustained_preserved,
            'scientific_stop':not(default_memory and stored_memory and prefix_preserved and sustained_preserved)}
