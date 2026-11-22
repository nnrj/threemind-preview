"""Independent arithmetic and full-state audit; does not advance scientific subjects."""
import argparse
from dataclasses import replace
from decimal import Decimal, localcontext
import gzip
import itertools
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0, str(Path(__file__).parent))
import study_resources as x
s = x.s
from threemind_kernels.local62_config import Local62Config
from threemind_kernels.mechanisms import ShortTermState


def score(path, q):
    points = s.unpack(path / 'process.json.gz')
    assert len(points) == 1502
    times = [p['time_us']-points[0]['time_us'] for p in points]
    assert times == [0] + list(range(0, 15000001, 10000))
    values = {}; errors = []
    with localcontext() as ctx:
        ctx.prec = 45
        for symbol in 'CE':
            for field in s.measure.FIELDS:
                pairs = [(t, Decimal(str(next((n[field] for n in p['nodes']
                    if n['channel'] == s.measure.TOKENS[symbol]), 0))))
                    for t, p in zip(times, points) if t >= 1000000]
                peak = max(v for _, v in pairs)
                area = sum(Decimal(b[0]-a[0])*(b[1]+a[1])/Decimal(2000000) for a,b in itertools.pairwise(pairs))
                expected = q['measures'][symbol][field]
                errors.extend((abs(float(peak)-expected['peak']), abs(float(area)-expected['area'])))
                values[symbol,field] = peak,area
        margin = float(values[q['target'],'activation'][0]-values[q['other'],'activation'][0])
        area = float(values[q['target'],'activation'][1]-values[q['other'],'activation'][1])
    errors.extend((abs(margin-q['signed_peak']), abs(area-q['signed_area'])))
    assert max(errors) < 1e-12
    return margin, max(errors)


def trace_measures(path, initial):
    raw = initial.to_dict()['config']
    cfg = Local62Config(**{k:v for k,v in raw.items() if k not in ('research_transport','resource_precheck')})
    counts = 0; available=[]; weight=[]; fast=[]; maximum=0.0; transport={}; saturation=0; node_count=0
    snapshots=[]
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for line in f:
            q=json.loads(line); counts+=1; transport=q.get('transport',{})
            for n in q['nodes']:
                maximum=max(maximum,n['activation']); node_count+=1
                saturation+=int(n['activation'] >= .95)
            current=[]
            for edge in q['edges']:
                weight.append(edge['weight'])
                state=edge['short_term']
                if state:
                    st=ShortTermState(**(state|{'time_us':int(state['time_us'])}))
                    st=st.recovered(q['time_us'],cfg.short_term())
                    available.append(st.available)
                    current.append({'source':edge['source'],'target':edge['target'],'weight':edge['weight'],
                        'available_at_time':st.available,'stored_time_us':state['time_us']})
                if edge.get('fast'):fast.append(edge['fast'].get('value',0))
            if q['time_us'] in (3900000,10000000,30000000,60000000,120000000,212200000):
                snapshots.append({'time_us':q['time_us'],'connections':current})
    assert counts == 2123, counts
    return {'records':counts,'mean_available_at_recorded_time':statistics.fmean(available) if available else None,
        'min_available_at_recorded_time':min(available,default=None),'mean_recorded_weight':statistics.fmean(weight),
        'maximum_activation':maximum,'fraction_node_records_at_least_0_95':saturation/node_count,
        'transport':transport,'resource_snapshots':snapshots}


def run(work):
    x.check(work)
    assert not any((work/p).exists() for p in ('in-flight.json','STOP'))
    summary=s.read(work/'summary.json'); tails=s.read(work/'tails.json')
    expected=144+(18 if summary['conditional']['run_old_inhibition_controls'] else 0)
    assert summary['stages']==len(summary['results'])==expected
    names=list(x.CONTROLS)+list(x.VARIANTS)
    if summary['conditional']['run_old_inhibition_controls']:names+=list(x.FALLBACK)
    index=s.read(work/'cases.json'); matrix=[]; states=[]; errors=[]; processes=0
    for name in names:
        blocks=[]
        for block in (0,1):
            margins=[]; parent=None; teaching=None; wall=0.
            for cue in ('train','AB','DB'):
                folder=x.folder(work,name,block,cue); q=s.read(folder/'result.json')
                initial=x.state_at(folder,'initial'); final=x.state_at(folder,'final')
                assert initial.digest==q['initial_sha256'] and final.digest==q['final_sha256']
                assert int(final.to_dict()['time_us'])==q['time_us']
                wall+=q['wall_seconds']
                if name not in x.CONTROLS:
                    assert q in summary['results']
                    assert x.create(name,state=final).capture_state().digest==final.digest
                    for k,v in x.condition(name)['patch'].items():
                        assert final.to_dict()['config'][k]==v,(name,cue,k)
                if cue=='train':
                    assert int(initial.to_dict()['time_us'])==0 and q['time_us']==212200000
                    assert q['parent_sha256'] is None; parent=final
                    teaching=trace_measures(folder/'teaching.jsonl.gz',initial)
                else:
                    assert q['parent_sha256']==parent.digest
                    assert initial.to_dict()['time_us']==parent.to_dict()['time_us']
                    if name not in x.CONTROLS:
                        copy=x.create(name,state=parent)
                        patch=index[f'history/s{block}/101/d1/{cue}']['patch']|x.condition(name)['patch']
                        copy.reconfigure(replace(copy.config,**patch))
                        assert copy.capture_state().digest==initial.digest
                    margin,error=score(folder,q);margins.append(margin);errors.append(error);processes+=1
                states.append({'folder':folder.relative_to(work).as_posix(),'initial':initial.digest,'final':final.digest})
            blocks.append({'block':block,'AB':margins[0],'DB':margins[1],
                'passed':all(v>1e-6 for v in margins),'minimum_margin':min(margins),
                'wall_seconds':wall,'teaching':teaching})
        matrix.append({'variant':name,'reused':name in x.CONTROLS,'blocks':blocks,
            'passed_blocks':sum(b['passed'] for b in blocks)})
    # Factorial effects are paired deterministic contrasts, not population p-values.
    table={r['variant']:r for r in matrix}; contrasts=[]
    for mode in ('stable','default'):
        for gate in ('g04','g0'):
            for resource in ('r08','full'):
                for block in (0,1):
                    for cue in ('AB','DB'):
                        a=table[f'{mode}-{gate}-{resource}']['blocks'][block][cue]
                        b=table[f'{mode}-{gate}-r8']['blocks'][block][cue]
                        cc=table[f'{mode}-g4-{resource}']['blocks'][block][cue]
                        d=table[f'{mode}-g4-r8']['blocks'][block][cue]
                        contrasts.append({'mode':mode,'gate':gate,'resource':resource,'block':block,'cue':cue,
                            'interaction':a-b-cc+d,'combined_change':a-d,'threshold_change':b-d,'resource_change':cc-d})
    assert tails['stages']==len(tails['results'])==8
    for q in tails['results']:
        folder=work/'tails'/q['variant']/str(q['block']); initial=x.state_at(folder,'initial');final=x.state_at(folder,'final')
        assert initial.digest==q['parent_sha256']==x.state_at(x.folder(work,q['variant'],q['block'],'train'),'final').digest
        assert final.digest==q['final_sha256']; assert q['rows'][-1]['state_sha256']==final.digest
        assert all(b['time_us']>a['time_us'] for a,b in itertools.pairwise(q['rows']))
        states.append({'folder':folder.relative_to(work).as_posix(),'initial':initial.digest,'final':final.digest})
    output={'material_blocks':2,'new_stages':expected,'reused_stages':24,'tail_stages':8,
        'matrix':matrix,'factorial_contrasts':contrasts,'tails':tails,'processes':processes,'states':2*len(states),
        'maximum_arithmetic_error':max(errors),'execution_wall_seconds':sum(q['wall_seconds'] for q in summary['results']),
        'modern_route_recovered':any(q['passed_blocks']==2 for q in matrix if q['variant'] in x.VARIANTS)}
    s.write(work/'analysis.json',output)
    s.write(work/'audit.json',{'passed':True,'scientific_stop':False,'states':2*len(states),'processes':processes,
        'maximum_arithmetic_error':max(errors),'state_hashes':states})
    print(json.dumps({'states':output['states'],'processes':processes,'modern_recovered':output['modern_route_recovered'],
        'matrix':[{k:v for k,v in q.items() if k!='blocks'}|{'margins':[[b['AB'],b['DB']] for b in q['blocks']]} for q in matrix]}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
