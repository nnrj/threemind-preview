"""Retrospective, read-only diagnostics; does not alter preregistered endpoints."""
import argparse,json
from pathlib import Path
from analyze import read

def diagnose(work):
    x=read(work/'analysis-v1.json');rows=[]
    for o in range(8):
        queries=[]
        for i in range(26):
            r=read(work/f'origins/o{o}/intact/result-{i:03d}.json.gz')
            queries.extend(dict(problem=i,**q) for step in r['steps'] for q in step['queries'])
        nz=[q for q in queries if abs(q['score'])>1e-12]
        graphs=[g for g in x['descriptive_graph_samples'] if g['arm']=='intact' and g['origin']==o]
        first_zero=next((g for g in graphs if g['edges']==0),None)
        rows.append(dict(origin=o,queries=len(queries),nonzero=len(nz),
                         last_nonzero_read_us=nz[-1]['read_us'] if nz else None,
                         last_nonzero_problem=nz[-1]['problem'] if nz else None,
                         first_zero_edge_boundary=first_zero))
    out=dict(schema='threemind.sat-retrospective-diagnostic/1',analysis_role='post hoc descriptive; no new intervention',
             score_tolerance=1e-12,training_ended_us=34000000,origins=rows,
             total_queries=sum(r['queries'] for r in rows),total_nonzero=sum(r['nonzero'] for r in rows))
    target=work/'diagnostic-v1.json';raw=json.dumps(out,ensure_ascii=False,indent=2).encode()
    if target.exists():assert target.read_bytes()==raw
    else:
        with target.open('xb') as f:f.write(raw)
    print(json.dumps(out))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();diagnose(a.work)
