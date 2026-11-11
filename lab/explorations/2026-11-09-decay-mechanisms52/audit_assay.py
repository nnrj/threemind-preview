"""Independent saved-JSON verification; no kernel or primary-analysis imports."""
import gzip
import hashlib
import json
import math
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')
ROOT=Path(__file__).resolve().parents[3]

def read(p):
    raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    analysis=read(WORK/'analysis-v1.json');cases=read(WORK/'cases.json')
    assert len(cases)==1920 and len({x['seed'] for x in cases})==8
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json'))
    for rel,h in read(WORK/'runner-manifest.json').items():assert sha(ROOT/rel)==h
    official={r['case']['key']:r for r in analysis['rows']};data={};count=0;seconds=0
    for c in cases:
        folder=WORK/'subjects'/c['key'];prior=read(folder/'birth.json.gz')
        assert int(prior['core']['time_us'])==0
        for stage in ('teaching','probe'):
            receipt=read(folder/stage/'complete.json');state=read(WORK/receipt['state_file'])
            assert sha(WORK/receipt['state_file'])==receipt['sha256']
            assert sha(WORK/receipt['result_file'])==receipt['result_sha256']
            assert digest(prior)==receipt['before_sha256'] and digest(state)==receipt['after_sha256']
            assert int(prior['core']['time_us'])==int(receipt['start_us'])
            assert int(state['core']['time_us'])==int(receipt['end_us'])
            seconds+=(int(receipt['end_us'])-int(receipt['start_us']))/1e6
            assert prior['mapping']==state['mapping'] and prior['identity']==state['identity']
            prior=state;count+=1
        taught=read(folder/'teaching/result.json.gz');result=read(folder/'probe/result.json.gz')
        ports={'cue',f"out{c['history']}"}
        initial={(x['source'],x['target']) for x in taught['edges'] if {x['source_symbol'],x['target_symbol']}==ports}
        actual={(x['source'],x['target']) for x in result['before']['edges']}
        own=official[c['key']]
        assert own['taught_core_sha256']==digest(read(folder/'teaching/whole.json.gz')['core'])
        assert own['pre_probe_sha256']==digest(result['before']) and own['baseline_sha256']==digest(result['baseline'])
        assert own['formed']==(len(initial)==2) and own['surviving']==len(initial&actual)
        values=[]
        for i in range(20):
            for channel in ('out0','out1'):
                for field in ('activation','inhibition','direct','associative'):
                    values.append(result['response']['raw'][i][channel][field]-result['baseline']['raw'][i][channel][field])
        assert values==own['response_vector']
        # Independently evaluate the registered 30-day conditional formula.
        saved=read(folder/'teaching/whole.json.gz')['core'];cfg=saved['config'];predictions=[]
        for row in saved['edges']:
            if (row['source'],row['target']) not in initial:continue
            duration=(int(saved['time_us'])-int(row['state_us']))/1e6+2592000
            rate=cfg['memory_half_life_decay_rate'] if cfg['retention_relaxation_enabled'] else 0.
            h=row['half_life'];minimum=cfg['memory_half_life_min_s']
            fall=min(duration,(h-minimum)/rate) if rate else 0.
            end=max(minimum,h-rate*duration)
            age=(math.log(h/end)/rate if fall else 0.)+(duration-fall)/end
            if c['curve']=='exponential':value=row['weight']*math.exp(-math.log(2)*age)
            elif c['curve']=='power-law':value=math.fsum(amount/(1+old_age+age) for amount,old_age in row['decay_contributions'])
            else:value=math.fsum(amount/(1+math.log1p((math.e-1)*(old_age+age))) for amount,old_age in row['decay_contributions'])
            predictions.append(value)
        assert len(predictions)==len(own['forecast_30days'])
        assert all(math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-14) for a,b in zip(predictions,own['forecast_30days']))
        assert own['finite_fading']==(len(predictions)==2 and all(x<cfg['prune_weight'] for x in predictions))
        data[c['origin'],c['curve'],c['relaxation'],c['course'],c['history'],c['delay'],c['cue']]=dict(
            values=values,formed=len(initial)==2,surviving=len(initial&actual),
            finite=len(predictions)==2 and all(x<cfg['prune_weight'] for x in predictions))
    for item in analysis['origins']:
        for course,report in item['courses'].items():
            differences=[]
            for delay in (1,300):
                prefix=(item['origin'],item['curve'],item['relaxation'],course)
                a=data[*prefix,0,delay,True]['values'];a0=data[*prefix,0,delay,False]['values']
                b=data[*prefix,1,delay,True]['values'];b0=data[*prefix,1,delay,False]['values']
                differences.append([(y-y0)-(x-x0) for x,x0,y,y0 in zip(a,a0,b,b0)])
            a,b=differences;na=math.sqrt(sum(x*x for x in a)/160);nb=math.sqrt(sum(x*x for x in b)/160)
            cosine=sum(x*y for x,y in zip(a,b))/(160*na*nb) if na and nb else None
            passed=na>1e-4 and nb>1e-4 and nb>=.1*na and cosine>=.8
            assert passed==report['process']['passed']
            parts={(h,d,q):data[item['origin'],item['curve'],item['relaxation'],course,h,d,q]
                for h in (0,1) for d in (1,300) for q in (True,False)}
            assert report['formed']==all(x['formed'] for x in parts.values())
            assert report['survives']==all(parts[h,300,True]['formed'] and parts[h,300,True]['surviving']==2 for h in (0,1))
            assert report['forgotten']==all(parts[h,300,True]['formed'] and parts[h,300,True]['surviving']==0 for h in (0,1))
            assert report['finite_fading']==all(x['finite'] for x in parts.values())
    for condition in analysis['conditions']:
        selected=[x for x in analysis['origins'] if x['curve']==condition['curve'] and x['relaxation']==condition['relaxation']]
        assert len(selected)==8
        for course,counts in condition['counts'].items():
            for field in ('formed','survives','forgotten','finite_fading'):
                assert counts[field]==sum(x['courses'][course][field] for x in selected)
            assert counts['process']==sum(x['courses'][course]['process']['passed'] for x in selected)
        count=condition['counts']
        structure=count['weak']['forgotten']>=6 and all(count[c]['survives']>=6 for c in ('strong','spaced'))
        process=all(count[c]['process']>=6 for c in ('strong','spaced'))
        finite=all(count[c]['finite_fading']>=6 for c in ('strong','spaced'))
        assert condition['selection']==dict(structure=structure,process=process,finite_fading=finite,
            all=structure and process and finite)
    assert count==analysis['complete_boundaries']==3840
    output=dict(passed=True,sequences=1920,independent_origins=8,complete_boundaries=count,
        aggregate_internal_seconds=seconds,method='independent JSON hashes, schedule identities, raw four-field arithmetic and direct curve formulas; no subject loading')
    with (WORK/'independent-audit-v1.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2)
    print(json.dumps(output))


if __name__=='__main__':main()
