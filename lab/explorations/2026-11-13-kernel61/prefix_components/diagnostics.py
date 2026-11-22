"""Dated secondary explanation from completed R51t6 originals; no stimulation."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import components_study as h
import audit_source

def diagnose(work):
    h.check(work);assert h.read(work/'audit.json')['passed']
    exact=[];differences=[];process=[]
    for block in (0,1):
        for material in (f'short/train-{block}',f'history/s{block}/101/d1/AB',f'history/s{block}/101/d1/DB'):
            ref=work/'cases/reference'/material;refstate=h.e.storage.image(ref/'final.rstate').to_dict()
            points=h.e.unpacked(ref/'trajectory.json.xz')['points']
            for variant in ('novelty-off','novelty-weight-only','novelty-stability-only'):
                f=work/'cases'/variant/material;st=h.e.storage.image(f/'final.rstate').to_dict()
                a=h.scientific_state(refstate);b=h.scientific_state(st)
                exact.append({'block':block,'material':material,'variant':variant,
                              'scientific_state_exact':a==b,'whole_node_process_exact':points==h.e.unpacked(f/'trajectory.json.xz')['points']})
        ref=h.e.storage.image(work/'cases/reference'/f'short/train-{block}/final.rstate').to_dict()
        alt=h.e.storage.image(work/'cases/window'/f'short/train-{block}/final.rstate').to_dict()
        channels={n['id']:n['channel'] for n in ref['nodes']};names={v:k for k,v in h.e.materials.TOKENS.items()}
        src={(e['source'],e['target']):e for e in ref['edges']};dst={(e['source'],e['target']):e for e in alt['edges']}
        assert set(src)==set(dst)
        for key in src:
            if channels[key[0]] in names and channels[key[1]] in names:
                differences.append({'block':block,'source':names[channels[key[0]]],'target':names[channels[key[1]]],
                    'reference_weight':src[key]['weight'],'window_weight':dst[key]['weight'],
                    'difference':dst[key]['weight']-src[key]['weight'],
                    'reference_stability':src[key]['stability'],'window_stability':dst[key]['stability']})
    for c in h.read(work/'cases.json'):
        if c['kind']!='probe':continue
        points=h.e.unpacked(work/'cases'/c['key']/'trajectory.json.xz')['points'];chosen={}
        for rel in (990000,1100000,2000000):
            p=next(p for p in points if p['time_us']==c['probe_start_us']+rel)
            nodes={n['channel']:n for n in p['nodes']}
            chosen[str(rel)]={name:{f:nodes.get(ch,{}).get(f,0.) for f in ('activation','inhibition','direct','associative','trace')}
                for name,ch in h.e.materials.TOKENS.items()}
        process.append({'variant':c['variant'],'block':c['block'],'cue':c['cue'],'points':chosen})
    result={'kind':'secondary mechanistic explanation; primary criteria unchanged','analysis_sha256':h.s.sha(work/'analysis.json'),
        'exact_novelty_comparisons':exact,'window_weight_differences':differences,'process_localization':process,
        'source_audit':audit_source.audit(),'loaded_engines':0}
    h.s.base.original(work/'diagnostics.json',result)
    print(json.dumps({'exact_states':sum(x['scientific_state_exact'] for x in exact),'exact_processes':sum(x['whole_node_process_exact'] for x in exact),
                      'comparisons':len(exact),'source_audit':result['source_audit']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();diagnose(a.work)
