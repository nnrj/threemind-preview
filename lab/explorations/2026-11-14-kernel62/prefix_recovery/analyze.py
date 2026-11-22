"""Read-only independent scoring and channel-aligned teaching comparisons."""
import argparse
from decimal import Decimal,localcontext
import gzip
import json
from pathlib import Path
import importlib.util
_spec=importlib.util.spec_from_file_location('r51t7_study',Path(__file__).with_name('study.py'))
s=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(s)

def stream(path):
    with gzip.open(path,'rb') as f:
        for line in f:yield json.loads(line)

def values(row):
    d={}
    for n in row['nodes']:
        for f in s.measure.FIELDS:d[f'node/{n["channel"]}/{f}']=n[f]
    for e in row['edges']:
        for f in ('weight','stability','eligibility'):d[f'edge/{e["source"]}/{e["target"]}/{f}']=e[f]
    return d

def divergence(a,b):
    for x,y in zip(stream(a),stream(b),strict=True):
        assert x['time_us']==y['time_us']
        p,q=values(x),values(y)
        keys=sorted(set(p)|set(q))
        diff=[{'field':k,'old':p.get(k),'new':q.get(k)} for k in keys
              if k not in p or k not in q or abs(p[k]-q[k])>1e-12]
        if diff:return {'time_us':x['time_us'],'differences':diff}
    return None

def run(work):
    assert not (work/'in-flight.json').exists()
    rows=s.read(work/'summary.json')['results'];assert len(rows)==54
    matrix=[];max_error=0.;audited=[]
    for variant in s.VARIANTS:
        blocks=[]
        for block in (0,1):
            parent=None;margins=[]
            for cue in ('train','AB','DB'):
                folder=work/'cases'/variant/str(block)/cue;q=s.read(folder/'result.json')
                initial=s.ArtifactCodec.decode((folder/'initial.tmind').read_bytes())
                final=s.ArtifactCodec.decode((folder/'final.tmind').read_bytes())
                assert initial.digest==q['initial_sha256'] and final.digest==q['final_sha256']
                assert int(final.to_dict()['time_us'])==q['time_us']
                if cue=='train':parent=final.digest
                else:
                    assert q['parent_sha256']==parent
                    points=s.unpack(folder/'process.json.gz');assert len(points)==1502
                    assert [r['time_us']-points[0]['time_us'] for r in points]==[0]+list(range(0,15000001,10000))
                    def peak(symbol):
                        ch=s.measure.TOKENS[symbol]
                        return max(Decimal(str(next((n['activation'] for n in p['nodes'] if n['channel']==ch),0))) for p in points if p['time_us']-points[0]['time_us']>=1000000)
                    with localcontext() as ctx:
                        ctx.prec=45;value=float(peak(q['target'])-peak(q['other']))
                    error=abs(value-q['signed_peak']);assert error<1e-14;max_error=max(max_error,error);margins.append(value)
                audited.append({'key':q['key'],'initial':initial.digest,'final':final.digest})
            blocks.append({'block':block,'margins':margins,'passed':all(v>1e-6 for v in margins)})
        matrix.append({'variant':variant,'blocks':blocks,'passed_blocks':sum(x['passed'] for x in blocks)})
    traces={}
    reference=work/'cases/old51/1/train/teaching.jsonl.gz'
    for variant in s.VARIANTS:
        if variant!='old51':traces[variant]=divergence(reference,work/'cases'/variant/'1/train/teaching.jsonl.gz')
    analysis={'matrix':matrix,'first_divergence':traces,'maximum_arithmetic_error':max_error,'material_blocks':2,'stages':54}
    s.write(work/'analysis.json',analysis)
    s.write(work/'audit.json',{'passed':True,'stages':54,'states':108,'processes':36,'maximum_arithmetic_error':max_error,'states_sha256':audited})
    print(json.dumps(analysis,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
