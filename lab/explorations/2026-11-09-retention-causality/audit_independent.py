"""Independent arithmetic and preservation check using JSON only, no Core import."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
DEFAULT=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')

def read(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',branches_completed=112)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    official=read(work/'analysis-v1.json');counts=Counter();groups=0;seconds=0;total_bytes=0
    originals=read(work/'source-manifest.json');source=Path(originals['source'])
    for rel,meta in originals['files'].items():
        assert sha(source/rel)==meta['source_sha256']==sha(work/meta['copied_path'])
        total_bytes+=meta['bytes']
    for rel,h in read(work/'runner-manifest.json').items():assert sha(ROOT/rel)==h
    aggregates={};origin_scores={};retention={};cross={};curricula=[];adapters=set();baseline_replays=[];activity_residuals=[]
    heads=('sound','vision','action')
    for phase,arms in [('late',['baseline','target','matched','all']),('early',['baseline','target','all'])]:
        for i in range(8):
            for history in (0,1):
                for arm in arms:
                    root=work/f'{phase}/o{i}/h{history}/{arm}';parent=read(root/'parent.json.gz')
                    assert parent['seed']==26110900+i and parent['core']['dynamics']=='threemind.continuous-memory/5.1'
                    assert sha(work/parent['parent']['path'])==parent['parent']['sha256']
                    initial_map={n['id']:next(k for k,v in parent['mapping'].items() if v==n['channel']) for n in parent['core']['nodes']}
                    ports={'S0','S1','V0','V1','A0','A1','AO'}
                    if arm=='baseline':
                        levels=[]
                        for cues in ({'X0','X1','D0','D1'},{'Z0','Z1','Z2','Z3'}):
                            group=[v for v in parent['core']['edges'] if
                                (initial_map[v['source']] in cues and initial_map[v['target']] in ports) or
                                (initial_map[v['target']] in cues and initial_map[v['source']] in ports)]
                            levels.append(sum(parent['activity_sum'][initial_map[v['source']]]/max(1,parent['activity_n']) for v in group)/len(group))
                        activity_residuals.append(dict(phase=phase,origin=i,history=history,residual=abs(levels[0]-levels[1])))
                    xkeys={(v['source'],v['target']) for v in parent['core']['edges'] if
                        (initial_map[v['source']] in {'X0','X1'} and initial_map[v['target']] in ports) or
                        (initial_map[v['target']] in {'X0','X1'} and initial_map[v['source']] in ports)}
                    expected=digest(parent);before_time=int(parent['core']['time_us']);rows=[]
                    units=['intervention']+(['teaching-1','teaching-2'] if phase=='early' else [])+[f'trial-{j:03d}' for j in range(24)]
                    for unit in units:
                        folder=root/unit;c=read(folder/'complete.json');s=read(work/c['state_file']);r=read(folder/'result.json.gz')
                        assert c['before_sha256']==expected and c['after_sha256']==digest(s)
                        assert sha(work/c['state_file'])==c['sha256'] and sha(folder/'result.json.gz')==c['result_sha256']
                        assert int(c['start_us'])==before_time and int(c['end_us'])==int(s['core']['time_us'])
                        seconds+=(int(c['end_us'])-before_time)/1e6;before_time=int(c['end_us']);expected=digest(s)
                        assert s['adapter_digest']==s['frozen_digest']==parent['adapter_digest']
                        assert s['core']['config']==parent['core']['config'] and s['mapping']==parent['mapping']
                        assert s['core']['silenced_edges']==parent['core']['silenced_edges']
                        if arm=='baseline' and unit!='intervention':
                            rel=f'origins/o{i}/h{history}/'+('intact/' if unit.startswith('trial-') else '')+unit+'/whole.json.gz'
                            original_state=read(source/rel)
                            for field in s:
                                if field not in {'identity','cursor','parent'}:assert s[field]==original_state[field],(phase,i,history,unit,field)
                            baseline_replays.append(dict(branch=str(root.relative_to(work)),unit=unit,source_path=rel,source_sha256=sha(source/rel),all_nonidentity_fields_equal=True))
                        for ref in s['adapter_refs'].values():
                            for name,h in ref['files'].items():
                                p=work/ref['path']/name
                                if str(p) not in adapters:assert sha(p)==h;adapters.add(str(p))
                        if unit=='intervention':assert int(c['end_us'])==int(c['start_us']);counts['intervention']+=1
                        elif unit.startswith('teaching-'):
                            counts['teaching']+=1;t=r['teaching'];waits=t['waits']
                            assert [(w['end_us']-w['start_us'])/1e6 for w in waits[-3:]]==[2,6,18]
                            original=read(work/f'reference/origins/o{i}/h{history}/{unit}/result.json.gz')['teaching']
                            # Teacher sequence and dose are fixed; answers to review questions may differ.
                            assert t['lessons']==original['lessons'] and t['waits']==original['waits']
                            assert [q['case'] for q in t['correction_questions']]==[q['case'] for q in original['correction_questions']]
                            curricula.append(dict(branch=str(root.relative_to(work)),unit=unit,lessons=len(t['lessons']),same_teacher_sequence=True))
                        else:
                            counts['trial']+=1;rows.append(r)
                            assert int(c['end_us'])-int(c['start_us'])==3000000
                            for w in (r['first'],r['second']):
                                assert len(w['raw'])==len(w['frame_times_us'])==20 and len(w['indices'])==8
                                assert all(len(w['frames'][head])==20 for head in heads)
                                assert w['indices']==[0,3,5,8,11,14,16,19]
                    groups+=1
                    key=phase+':'+arm;by={name:[r for r in rows if r['case']['kind']==name] for name in ('old','clear','ambiguous')}
                    scores={}
                    for name in ('old','clear'):
                        scores[name]={'correct':sum(all(r['first']['predictions'][head]==r['case']['expected'] for head in heads) for r in by[name]),'n':len(by[name])}
                    for head in heads:scores[head]={'correct':sum(r['first']['predictions'][head]==r['case']['expected'] for r in by['clear']),'n':len(by['clear'])}
                    scores['view']={'correct':sum(r['first']['predictions']['action']==2 for r in by['ambiguous']),'n':len(by['ambiguous'])}
                    scores['exit']={'correct':sum(r['second']['predictions']['action']==r['case']['actual'] for r in by['ambiguous']),'n':len(by['ambiguous'])}
                    conflicts=[r for r in by['clear'] if r['case']['conflict']]
                    scores['revision']={'correct':sum(all(r['second']['predictions'][head]==r['case']['actual'] for head in heads) for r in conflicts),'n':len(conflicts)}
                    origin_scores[(phase,i,history,arm)]=scores
                    retention[(phase,i,history,arm)]=len(xkeys&{(v['source'],v['target']) for v in s['core']['edges']})/len(xkeys)
                    cross[(phase,i,history,arm)]=[r['first']['predictions'] for r in by['clear']]
                    dest=aggregates.setdefault(key,{k:{'correct':0,'n':0} for k in scores})
                    for k,v in scores.items():
                        for n in ('correct','n'):dest[k][n]+=v[n]
    assert counts=={'intervention':112,'teaching':96,'trial':2688} and groups==112
    assert aggregates==official['aggregate']
    per=[]
    for i in range(8):
        def fraction(phase,arm,key):
            both=[origin_scores[phase,i,h,arm][key] for h in (0,1)]
            return sum(x['correct'] for x in both)/sum(x['n'] for x in both)
        def benefit(p,a):return fraction(p,a,'clear')-fraction(p,'baseline','clear')
        def safe(p,a):return fraction(p,'baseline','old')-fraction(p,a,'old')<=.125
        q1=all(retention['late',i,h,'target']>=.9 and retention['late',i,h,'baseline']<=.1 for h in (0,1))
        q2=q1 and benefit('late','target')>=.25 and benefit('late','target')-benefit('late','matched')>=.125 and safe('late','target')
        q3={a:benefit('early',a)>=.25 and safe('early',a) for a in ('target','all')}
        q4={}
        for key in aggregates:
            p,a=key.split(':');both=[origin_scores[p,i,h,a]['clear'] for h in (0,1)]
            changed=sum(all(x[k]!=y[k] for k in heads) for x,y in zip(cross[p,i,0,a],cross[p,i,1,a]))/8
            q4[key]=all(x['correct']/x['n']>=.75 for x in both) and changed>=.5
        per.append(dict(Q1=q1,Q2=q2,Q3=q3,Q4=q4))
    verdict={k:sum(x[k] for x in per) for k in ('Q1','Q2')}
    verdict['Q3']={a:sum(x['Q3'][a] for x in per) for a in ('target','all')}
    verdict['Q4']={k:sum(x['Q4'][k] for x in per) for k in aggregates}
    assert verdict==official['successes']
    out=dict(passed=True,method='independent JSON arithmetic and hash checks; no Core restored',counts=dict(counts),chains=groups,
        total_computed_internal_seconds=seconds,source_files_verified=len(originals['files']),source_bytes=total_bytes,
        adapter_files_verified=len(adapters),aggregate=aggregates,successes=verdict,curricula=curricula,
        baseline_replays=baseline_replays,baseline_whole_replay_count=len(baseline_replays),
        retrospective_activity_matching=activity_residuals)
    target=work/'independent-audit-v1.json'
    with target.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,sort_keys=True)
    print(json.dumps({k:v for k,v in out.items() if k not in ('curricula','aggregate','baseline_replays','retrospective_activity_matching')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=DEFAULT);a=p.parse_args();run(a.work.resolve())
