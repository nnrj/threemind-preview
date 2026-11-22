"""Audit every complete state and independently recalculate all process scores."""
import argparse
from decimal import Decimal,localcontext
import itertools
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import run_transport as rt
import run_threshold as rh
import analyze as initial_analysis
import run_exchanges as exchanges
s=rt.s

def process(folder,q):
    points=s.unpack(folder/'process.json.gz')
    assert len(points)==1502
    times=[p['time_us']-points[0]['time_us'] for p in points]
    assert times==[0]+list(range(0,15000001,10000))
    series={};error=0.
    with localcontext() as ctx:
        ctx.prec=45
        for symbol in 'CE':
            for field in s.measure.FIELDS:
                pairs=[(t,Decimal(str(next((n[field] for n in p['nodes'] if n['channel']==s.measure.TOKENS[symbol]),0))))
                       for t,p in zip(times,points) if t>=1000000]
                area=sum(Decimal(b[0]-a[0])*(b[1]+a[1])/Decimal(2000000) for a,b in itertools.pairwise(pairs))
                peak=max(v for _,v in pairs)
                actual=q['measures'][symbol][field]
                error=max(error,abs(float(area)-actual['area']),abs(float(peak)-actual['peak']))
                series[symbol,field]=(peak,area)
        margin=series[q['target'],'activation'][0]-series[q['other'],'activation'][0]
        area=series[q['target'],'activation'][1]-series[q['other'],'activation'][1]
        error=max(error,abs(float(margin)-q['signed_peak']),abs(float(area)-q['signed_area']))
    assert error<1e-12,(folder,error)
    return float(margin),error

def run(work):
    rt.check(work);rh.check(work)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    groups=[('',54),('transport',12),('threshold',12)]
    if (work/'exchanges/summary.json').exists():groups.append(('exchanges',16))
    states=[];matrix=[];errors=[];stages=0;processes=0
    for group,count in groups:
        root=work/group;rows=s.read(root/'summary.json')['results'];assert len(rows)==count
        stages+=len(rows)
        values={}
        for q in rows:
            folder=root/'cases'/q['key'];assert s.read(folder/'result.json')==q
            use_research=(folder/'initial.rstate.gz').exists()
            if use_research:
                before=rt.get(folder/'initial.rstate.gz');after=rt.get(folder/'final.rstate.gz')
                assert rt.r.ResearchEngine(state=after).capture_state().digest==after.digest
            else:
                before=s.ArtifactCodec.decode((folder/'initial.tmind').read_bytes());after=s.ArtifactCodec.decode((folder/'final.tmind').read_bytes())
            assert before.digest==q['initial_sha256'] and after.digest==q['final_sha256']
            assert int(after.to_dict()['time_us'])==q['time_us']
            states.append({'key':group+'/'+q['key'],'initial':before.digest,'final':after.digest})
            if q['cue']=='train':
                assert q['parent_sha256'] is None and q['time_us']==212200000
            else:
                if group=='exchanges':
                    exchanges.check(work)
                    parent=rt.get(work/q['parent_file'])
                    donor=rt.get(work/q['donor_file'])
                    intervention=s.read(folder/'intervention.json')
                    pre=rt.get(folder/'before-intervention.rstate.gz')
                    assert intervention['before']==pre.digest and intervention['after']==before.digest
                    assert intervention['parent']==parent.digest and intervention['donor']==donor.digest
                    assert intervention['time_advanced_us']==0
                    assert exchanges.differences(pre.to_dict(),before.to_dict())==intervention['changes']
                    if q['kind']=='weights':
                        assert len(intervention['changes'])==8
                        assert all(x['path'].startswith('/edges/') and x['path'].endswith('/weight') for x in intervention['changes'])
                        donor_weights={(x['source'],x['target']):x['weight'] for x in donor.to_dict()['edges']}
                        for edge in before.to_dict()['edges']:
                            if [edge['source'],edge['target']] in intervention['task_connections']:
                                assert edge['weight']==donor_weights[edge['source'],edge['target']]
                else:
                    p=root/'cases'/q['variant']/str(q['block'])/'train'
                    parent=rt.get(p/'final.rstate.gz') if use_research else s.ArtifactCodec.decode((p/'final.tmind').read_bytes())
                assert parent.digest==q['parent_sha256']
                assert before.to_dict()['time_us']==parent.to_dict()['time_us']
                margin,error=process(folder,q);errors.append(error);processes+=1
                values.setdefault(q['variant'],{}).setdefault(q['block'],{})[q['cue']]=margin
        for variant,blocks in values.items():
            result=[]
            for block,cues in sorted(blocks.items()):
                assert set(cues)=={'AB','DB'}
                result.append({'block':block,'AB':cues['AB'],'DB':cues['DB'],'passed':all(v>1e-6 for v in cues.values())})
            assert len(result)==2
            matrix.append({'group':group or 'initial','variant':variant,'blocks':result,'passed_blocks':sum(x['passed'] for x in result)})
    comparisons={}
    for group in ('transport','threshold'):
        for variant in s.read(work/group/'frozen.json')['variants']:
            comparisons[group+'/'+variant]=initial_analysis.divergence(work/'cases/old51/1/train/teaching.jsonl.gz',work/group/'cases'/variant/'1/train/teaching.jsonl.gz')
    resource_first=None
    for x,y in zip(initial_analysis.stream(work/'transport/cases/old-emission/1/train/teaching.jsonl.gz'),
                   initial_analysis.stream(work/'threshold/cases/threshold-old-inhibition/1/train/teaching.jsonl.gz'),strict=True):
        x.pop('transport',None);y.pop('transport',None)
        diff=exchanges.differences(x,y)
        if diff:
            resource_first={'time_us':x['time_us'],'differences':diff,
                            'connection_order':[[e['source'],e['target']] for e in x['edges']]};break
    result={'stages':stages,'states':len(states)*2,'processes':processes,'material_blocks':2,'matrix':matrix,
            'maximum_arithmetic_error':max(errors),'first_divergence_additional':comparisons,'resource_first_divergence':resource_first,
            'intervention_states':16 if len(groups)==4 else 0}
    s.write(work/'final-analysis.json',result)
    s.write(work/'final-audit.json',{'passed':True,**{k:result[k] for k in ('stages','states','processes','maximum_arithmetic_error')},'states_sha256':states})
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
