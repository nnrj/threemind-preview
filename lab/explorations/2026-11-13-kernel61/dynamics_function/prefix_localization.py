"""Read-only localization on completed R51t2 recordings; no kernel construction."""
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as h

def analyze(work):
    h.check(work);assert h.read(work/'audit.json')['passed']
    ids=h.e.materials.TOKENS;cases=h.read(work/'cases.json');rows=[]
    for c in cases:
        if c['group']!='prefix' or c['kind']!='probe':continue
        folder=work/'cases'/c['key'];points=h.e.unpacked(folder/'trajectory.json.xz')['points']
        selected={}
        for rel in (100000,990000,1100000,2000000):
            p=next(p for p in points if p['time_us']==c['probe_start_us']+rel)
            nodes={n['channel']:n for n in p['nodes']}
            selected[str(rel)]={name:{f:nodes.get(ch,{}).get(f,0.) for f in ('activation','inhibition','direct','associative','trace')}
                for name,ch in ids.items()}
        projection=h.e.unpacked(folder/'projections.json.xz')['before_probe']['graph']
        edges=[]
        reverse={v:k for k,v in ids.items()}
        for ed in projection['edges']:
            if ed['source'] in reverse and ed['target'] in reverse:
                edges.append({'source':reverse[ed['source']],'target':reverse[ed['target']],
                    'weight':ed['weight'],'fast':ed['fast'],'short_term':ed['short_term']})
        rows.append({'variant':c['variant'],'block':c['block'],'cue':c['cue'],'points':selected,'task_edges':edges})
    combined=[]
    for variant in sorted({r['variant'] for r in rows}):
        for block in (0,1):
            a=next(r for r in rows if (r['variant'],r['block'],r['cue'])==(variant,block,'AB'))
            b=next(r for r in rows if (r['variant'],r['block'],r['cue'])==(variant,block,'DB'))
            assert a['task_edges']==b['task_edges'],'diagnostic probes must have same teaching parent'
            aa=a['points']['990000'];bb=b['points']['990000'];post_a=a['points']['1100000'];post_b=b['points']['1100000']
            combined.append({'variant':variant,'block':block,
                'prefix_node_contrast_before_B':{'AB_A_minus_D':aa['A']['activation']-aa['D']['activation'],
                    'DB_D_minus_A':bb['D']['activation']-bb['A']['activation']},
                'C_minus_E_100ms_after_B':{'AB':post_a['C']['activation']-post_a['E']['activation'],
                    'DB':post_b['C']['activation']-post_b['E']['activation']}})
    result={'analysis':'predeclared process localization; no new stimulation or refitting','source_analysis_sha256':h.s.sha(work/'analysis.json'),
        'rows':rows,'contrasts':combined,'observer_interval_us':10000,'B_time_relative_us':1000000,'constructed_engines':0}
    h.s.base.original(work/'prefix-localization.json',result)
    print(json.dumps(combined),flush=True)

if __name__=='__main__':analyze(Path(sys.argv[1]))
