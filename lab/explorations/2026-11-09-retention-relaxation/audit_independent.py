"""Independent JSON-only R45 arithmetic, identities and preservation checks."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1')
ARMS=tuple(f'{b}-{r}' for b in ('natural','raised') for r in ('default','slow','off'))
RATES={'default':.125,'slow':.0125,'off':0.}
HEADS=('sound','vision','action')
PORTS={'S0','S1','V0','V1','A0','A1','AO'}


def read(p):
    raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',branches_completed=96)
    assert not (WORK/'STOP').exists() and not (WORK/'in-flight.json').exists()
    official=read(WORK/'analysis-v1.json');total=Counter();aggregate={};scores={};cross={};seconds=0
    structure_checks=[];off_comparisons=0
    for rel,h in read(WORK/'runner-manifest.json').items():assert sha(ROOT/rel)==h
    sources=read(WORK/'source-manifest.json')
    for rel,m in sources['files'].items():assert sha(Path(sources['source'])/rel)==m['source_sha256']==sha(WORK/m['copied_path'])
    for i in range(8):
        for history in (0,1):
            for arm in ARMS:
                root=WORK/f'origins/o{i}/h{history}/{arm}';parent=read(root/'parent.json.gz')
                assert parent['seed']==26110900+i
                assert sha(WORK/parent['parent']['path'])==parent['parent']['sha256']
                names={n['id']:next(k for k,v in parent['mapping'].items() if v==n['channel']) for n in parent['core']['nodes']}
                initial={(x['source'],x['target']) for x in parent['core']['edges'] if
                    (names[x['source']] in {'X0','X1'} and names[x['target']] in PORTS) or
                    (names[x['target']] in {'X0','X1'} and names[x['source']] in PORTS)}
                prev=digest(parent);time_us=int(parent['core']['time_us']);rows=[];last_h={}
                for unit in ['intervention','teaching-1','teaching-2']+[f'trial-{j:03d}' for j in range(24)]:
                    c=read(root/unit/'complete.json');s=read(WORK/c['state_file']);r=read(root/unit/'result.json.gz')
                    assert c['before_sha256']==prev and c['after_sha256']==digest(s)
                    assert sha(WORK/c['state_file'])==c['sha256'] and sha(root/unit/'result.json.gz')==c['result_sha256']
                    assert int(c['start_us'])==time_us and int(c['end_us'])==int(s['core']['time_us'])
                    seconds+=(int(c['end_us'])-time_us)/1e6;time_us=int(c['end_us']);prev=digest(s)
                    assert s['core']['dynamics']=='threemind.continuous-memory/5.1'
                    cfg=dict(parent['core']['config'],memory_half_life_decay_rate=RATES[arm.split('-')[1]])
                    assert s['core']['config']==cfg and s['mapping']==parent['mapping']
                    assert s['adapter_digest']==s['frozen_digest']==parent['adapter_digest']
                    hs={}
                    for edge in s['core']['edges']:
                        dt=(time_us-int(edge['state_us']))/1e6
                        hs[(edge['source'],edge['target'])]=max(cfg['memory_half_life_min_s'],edge['half_life']-cfg['memory_half_life_decay_rate']*dt)
                    if arm.endswith('-off'):
                        for key in hs.keys()&last_h.keys():assert hs[key]>=last_h[key]-1e-10;off_comparisons+=1
                    last_h=hs
                    if unit=='intervention':
                        total['interventions']+=1;assert int(c['end_us'])==int(c['start_us'])
                        assert r['max_current_physical_change_at_reconfigure']<=1e-12
                    elif unit.startswith('teaching-'):
                        total['teaching']+=1
                        ref=read(WORK/f'reference/origins/o{i}/h{history}/{unit}/result.json.gz')['teaching'];t=r['teaching']
                        assert t['lessons']==ref['lessons'] and t['waits']==ref['waits']
                        assert [(v['end_us']-v['start_us'])/1e6 for v in t['waits'][-3:]]==[2,6,18]
                        assert [q['case'] for q in t['correction_questions']]==[q['case'] for q in ref['correction_questions']]
                    else:
                        total['trials']+=1;rows.append(r)
                        assert int(c['end_us'])-int(c['start_us'])==3000000
                        for window in ('first','second'):
                            assert len(r[window]['raw'])==len(r[window]['frame_times_us'])==20 and len(r[window]['indices'])==8
                            assert all(len(r[window]['frames'][head])==20 for head in HEADS)
                            assert r[window]['indices']==[0,3,5,8,11,14,16,19]
                    if unit in ('intervention','teaching-1','teaching-2','trial-023'):
                        retained=len(initial&set(hs))
                        reference=next(x for x in official['branches'] if (x['origin'],x['history'],x['arm'])==(i,history,arm))
                        stage=next(x for x in reference['structure'] if x['stage']==unit)
                        # Scientific retention uses stable directed-edge IDs, not merely channel names.
                        assert retained==stage['x_surviving'] and len(initial)==stage['x_initial']
                        structure_checks.append(dict(origin=i,history=history,arm=arm,stage=unit,stable_id_surviving=retained,initial=len(initial)))
                grouped={k:[r for r in rows if r['case']['kind']==k] for k in ('old','clear','ambiguous')}
                count={}
                for label,kind in (('old','old'),('new','clear')):
                    rs=grouped[kind];count[label]=dict(correct=sum(all(r['first']['predictions'][k]==r['case']['expected'] for k in HEADS) for r in rs),n=len(rs))
                for k in HEADS:count[k]=dict(correct=sum(r['first']['predictions'][k]==r['case']['expected'] for r in grouped['clear']),n=len(grouped['clear']))
                mixed=grouped['ambiguous'];conf=[r for r in grouped['clear'] if r['case']['conflict']]
                count['view']=dict(correct=sum(r['first']['predictions']['action']==2 for r in mixed),n=len(mixed))
                count['exit']=dict(correct=sum(r['second']['predictions']['action']==r['case']['actual'] for r in mixed),n=len(mixed))
                count['revision']=dict(correct=sum(all(r['second']['predictions'][k]==r['case']['actual'] for k in HEADS) for r in conf),n=len(conf))
                scores[i,history,arm]=count;cross[i,history,arm]=[r['first']['predictions'] for r in grouped['clear']]
                dest=aggregate.setdefault(arm,{k:dict(correct=0,n=0) for k in count})
                for k,v in count.items():
                    for field in ('correct','n'):dest[k][field]+=v[field]
    assert total==dict(interventions=96,teaching=192,trials=2304) and aggregate==official['aggregate']
    benefits=Counter();restore=Counter();effects={}
    for i in range(8):
        def frac(arm,key):
            rs=[scores[i,h,arm][key] for h in (0,1)];return sum(r['correct'] for r in rs)/sum(r['n'] for r in rs)
        for arm in ARMS:
            q=[scores[i,h,arm]['new'] for h in (0,1)]
            changed=sum(all(a[k]!=b[k] for k in HEADS) for a,b in zip(cross[i,0,arm],cross[i,1,arm]))/8
            restore[arm]+=all(x['correct']/x['n']>=.75 for x in q) and changed>=.5
            if arm.endswith('-default'):continue
            reference=arm.split('-')[0]+'-default';gain=frac(arm,'new')-frac(reference,'new');loss=frac(reference,'old')-frac(arm,'old')
            benefits[arm]+=gain>=.25 and loss<=.125
            effects.setdefault(arm,[]).append(gain)
    verdict=dict(R1=True,R2={a:benefits[a] for a in ARMS if a.startswith('natural') and not a.endswith('-default')},
        R3={a:benefits[a] for a in ARMS if a.startswith('raised') and not a.endswith('-default')},R4=dict(restore))
    assert verdict==official['successes']
    for arm,v in effects.items():assert v==official['effects'][arm]['individual']
    result=dict(passed=True,method='independently implemented JSON/hash arithmetic; no Core import or subject advancement',
        counts=dict(total),chains=96,complete_boundaries=sum(total.values()),total_internal_seconds=seconds,
        successes=verdict,aggregate=aggregate,off_monotonic_comparisons=off_comparisons,stable_id_structure_checks=structure_checks,
        source_files_verified=len(sources['files']))
    with (WORK/'independent-audit-v1.json').open('x',encoding='utf-8') as f:json.dump(result,f,sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ('aggregate','stable_id_structure_checks')}))


if __name__=='__main__':main()
