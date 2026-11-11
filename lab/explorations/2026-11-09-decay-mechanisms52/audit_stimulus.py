"""Independent R46b JSON arithmetic and continuity audit; standard library only."""
import gzip
import hashlib
import json
import math
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')
ROOT=Path(__file__).resolve().parents[3]
FIELDS=('activation','inhibition','direct','associative')


def read(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def norm(values):return math.sqrt(math.fsum(v*v for v in values)/len(values))


def decay(row,core):
    cfg=core['config'];duration=(int(core['time_us'])-int(row['state_us']))/1e6+2592000
    h=row['half_life'];minimum=cfg['memory_half_life_min_s']
    rate=cfg['memory_half_life_decay_rate'] if cfg['retention_relaxation_enabled'] else 0.
    fall=min(duration,(h-minimum)/rate) if rate else 0.
    end=max(minimum,h-rate*duration)
    age=(math.log(h/end)/rate if fall else 0.)+(duration-fall)/end
    if cfg['decay_curve']=='exponential':return row['weight']*math.exp(-math.log(2)*age)
    if cfg['decay_curve']=='power-law':return math.fsum(amount/(1+old_age+age) for amount,old_age in row['decay_contributions'])
    return math.fsum(amount/(1+math.log1p((math.e-1)*(old_age+age))) for amount,old_age in row['decay_contributions'])


def main(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','independent-audit-v1.json'))
    for rel,h in read(work/'runner-manifest.json').items():assert sha(ROOT/rel)==h
    cases=read(work/'cases.json');analysis=read(work/'analysis-v1.json')
    assert len(cases)==len(analysis['rows'])==960 and len({c['key'] for c in cases})==960
    assert len({c['seed'] for c in cases})==8
    official={r['case']['key']:r for r in analysis['rows']};data={};configs={};boundaries=0;seconds=0.
    for c in cases:
        folder=work/'subjects'/c['key'];previous=read(folder/'birth.json.gz')
        assert int(previous['core']['time_us'])==0 and previous['case']==c
        configs[c['origin'],c['curve'],c['relaxation'],c['arm']]=previous['core']['config']
        for stage in ('teaching','probe'):
            receipt=read(folder/stage/'complete.json');state=read(work/receipt['state_file'])
            assert sha(work/receipt['state_file'])==receipt['sha256'] and sha(work/receipt['result_file'])==receipt['result_sha256']
            assert digest(previous)==receipt['before_sha256'] and digest(state)==receipt['after_sha256']
            assert int(previous['core']['time_us'])==int(receipt['start_us']) and int(state['core']['time_us'])==int(receipt['end_us'])
            assert previous['mapping']==state['mapping'] and previous['identity']==state['identity']
            assert previous['core']['config']==state['core']['config']
            seconds+=(int(receipt['end_us'])-int(receipt['start_us']))/1e6;boundaries+=1;previous=state
        taught=read(folder/'teaching/result.json.gz');saved=read(folder/'teaching/whole.json.gz');result=read(folder/'probe/result.json.gz')
        sample=taught['samples']['immediate' if c['family']=='strong' else 'after_window']
        initial=[r for r in sample['graph']['edges'] if {r['source_symbol'],r['target_symbol']}=={'cue','out0'}]
        ids={(r['source'],r['target']) for r in initial}
        current=[r for r in result['before']['edges'] if (r['source'],r['target']) in ids]
        row=official[c['key']]
        assert row['formed']==(len(ids)==2) and row['surviving']==len(current)
        iw=math.fsum(r['weight'] for r in initial)/2;cw=math.fsum(r['weight'] for r in current)/2
        assert row['initial_mean_weight']==iw and row['current_mean_weight']==cw
        v=[result['response']['raw'][i]['out0'][f]-result['baseline']['raw'][i]['out0'][f] for i in range(20) for f in FIELDS]
        assert v==row['response_vector']
        assert row['taught_core_sha256']==digest(saved['core'])
        assert row['pre_probe_sha256']==digest(result['before']) and row['baseline_sha256']==digest(result['baseline'])
        raw={(r['source'],r['target']):r for r in saved['core']['edges']}
        predictions=[decay(raw[k],saved['core']) if k in raw else 0. for k in sorted(ids)]
        assert len(predictions)==len(row['forecast_30days'])
        assert all(math.isclose(x,y,rel_tol=1e-11,abs_tol=1e-14) for x,y in zip(predictions,row['forecast_30days']))
        fading=len(predictions)==2 and all(v<saved['core']['config']['prune_weight'] for v in predictions)
        assert fading==row['finite_fading']
        data[c['origin'],c['curve'],c['relaxation'],c['arm'],c['delay'],c['cue']]=dict(v=v,initial=iw,current=cw,
            survives=len(current)==2,fading=fading,taught=digest(saved['core']),before=digest(result['before']),baseline=digest(result['baseline']))
    byorigin={(r['origin'],r['curve'],r['relaxation']):r for r in analysis['origins']};calculated=[]
    for curve in ('exponential','inverse-logarithmic','power-law'):
        for relax in (True,False):
            counts={name:dict(immediate=0,structure=0,activity=0) for name in ('strong-gain','novelty-gain','overall-intensity')}
            retention={name:dict(structure=0,process=0,finite_fading=0) for name in ('strong-intensity','arrival-novelty')}
            for o in range(8):
                official_origin=byorigin[o,curve,relax];arms={}
                for arm in ('equal-drive-normal','strong-intensity','strong-gain-zero','arrival-novelty','arrival-gain-zero'):
                    get=lambda d,q:data[o,curve,relax,arm,d,q]
                    assert len({get(d,q)['taught'] for d in (1,300) for q in (True,False)})==1
                    effects={d:[x-y for x,y in zip(get(d,True)['v'],get(d,False)['v'])] for d in (1,300)}
                    for d in (1,300):
                        assert get(d,True)['before']==get(d,False)['before'] and get(d,True)['baseline']==get(d,False)['baseline']
                    early,late=norm(effects[1]),norm(effects[300])
                    cosine=math.fsum(x*y for x,y in zip(effects[1],effects[300]))/(80*early*late) if early and late else None
                    process=early>1e-4 and late>1e-4 and late>=.1*early and cosine>=.8
                    own=official_origin['arms'][arm]
                    assert own['effect']==effects and own['process']==dict(early_rms=early,late_rms=late,cosine=cosine,passed=process)
                    arms[arm]=dict(initial=get(1,True)['initial'],current=get(300,True)['current'],late=late,survives=get(300,True)['survives'])
                    if arm in retention:
                        retention[arm]['structure']+=get(300,True)['survives']
                        retention[arm]['process']+=process
                        retention[arm]['finite_fading']+=all(get(d,q)['fading'] for d in (1,300) for q in (True,False))
                for name,xn,yn in (('strong-gain','strong-intensity','strong-gain-zero'),('novelty-gain','arrival-novelty','arrival-gain-zero'),('overall-intensity','strong-intensity','equal-drive-normal')):
                    x,y=arms[xn],arms[yn]
                    verdict=dict(immediate=x['initial']-y['initial']>1e-8,
                        structure=x['survives'] and x['current']-y['current']>1e-6 and x['current']-y['current']>=.1*y['current'],
                        activity=x['late']>1e-4 and x['late']-y['late']>1e-6 and x['late']-y['late']>=.1*y['late'])
                    for field,value in verdict.items():
                        assert official_origin['comparisons'][name][field]['passed']==value
                        counts[name][field]+=value
                for x,y,only in (('strong-intensity','strong-gain-zero','intensity_gain'),('arrival-novelty','arrival-gain-zero','local_novelty_gain')):
                    xcfg,ycfg=configs[o,curve,relax,x],configs[o,curve,relax,y]
                    assert {k for k in xcfg if xcfg[k]!=ycfg[k]}=={only}
            calculated.append(dict(curve=curve,relaxation=relax,counts=counts,retention=retention,
                gates={name:{field:n>=6 for field,n in row.items()} for name,row in counts.items()}))
    assert calculated==analysis['conditions']
    assert boundaries==analysis['complete_boundaries']==1920 and seconds==analysis['internal_seconds']
    last=read(work/'current.json');assert last['unit']=='subjects/'+cases[-1]['key']+'/probe' and sha(work/last['state_file'])==last['sha256']
    out=dict(passed=True,script_sha256=sha(Path(__file__)),sequences=960,boundaries=boundaries,internal_seconds=seconds,
             matched_conditions=8,conditions=calculated,scope='Independent original-JSON continuity, formula and arithmetic checks; not external replication.')
    with (work/'independent-audit-v1.json').open('x',encoding='utf-8') as stream:json.dump(out,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!='conditions'}))


if __name__=='__main__':main(WORK)
