"""Read-only analysis of a frozen historical factor matrix."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prefix_cross as h
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m
e=h.e;s=h.s

def analyze(work):
    h.check(work);assert h.read(work/'summary.json')['complete']==54 and not (work/'in-flight.json').exists()
    rows=[];states=0;inputs=0
    for reused,cases in [(False,h.read(work/'cases.json')),(True,h.read(work/'reference-cases.json'))]:
        for c in cases:
            folder=work/('references' if reused else 'cases')/c['key'];r=h.read(folder/'result.json')
            assert r['status']=='complete' and r['kernel']=='threemind.continuous-memory/'+c['version']
            a=e.base.image(folder/'initial.tmind');z=e.base.image(folder/'final.tmind');states+=2
            assert a.digest==r['initial_sha256'] and z.digest==r['final_sha256']
            assert int(a.to_dict()['time_us'])==c['begin_us'] and int(z.to_dict()['time_us'])==c['end_us']
            assert a.to_dict()['dynamics']==z.to_dict()['dynamics']==r['kernel']
            if not reused:
                changed=e.base.image(folder/'intervened.tmind');assert changed.digest==r['intervened_sha256'];states+=1
                assert changed.to_dict()['config']==a.to_dict()['config']|c['patch']|c['cause_patch']
                assert z.to_dict()['config']==changed.to_dict()['config']
                if c['parent']:
                    parent=work/'cases'/c['parent'];assert a.digest==e.base.image(parent/'final.tmind').digest
                    assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(parent/'observer.json.xz')
                original=e.unpacked(folder/'inputs.json.xz');delivered=e.unpacked(folder/'delivered.json.xz')
                assert original==e.material_frames(c,work/'materials') and len(original)==len(delivered)==r['inputs'];inputs+=len(original)
                norm=lambda x:json.dumps({'stimulus':x['stimulus'],'source':x['source']},sort_keys=True)
                assert Counter(norm(x) for x in original)==Counter(norm(x) for x in delivered)
                assert all(x['stimulus']['time_us']==x['scheduled_time_us']==x['delivered_time_us'] and not x.get('labels') for x in delivered)
                with zipfile.ZipFile(folder/'milestones.zip') as zz:
                    for k,digest in r['snapshots'].items():assert e.base.ArtifactCodec.decode(zz.read(k+'.tmind')).digest==digest;states+=1
            assert e.unpacked(folder/'observer.json.xz')['input_bus']['pending']=={}
            if c['kind']=='probe':
                q=m.process(c,e.unpacked(folder/'trajectory.json.xz')['points'])
                q.update(version=c['version'],retention=c['retention'],novelty=c['novelty'],block=c['block'],variant=c['matrix_variant'],reused=reused)
                rows.append(q)
    matrix=h.matrix.aggregate(rows,m.EPS)
    comparison=h.matrix.compare(matrix,h.read(h.HISTORY/'analysis.json'))
    error=max(r['arithmetic_error'] for r in rows)
    result={'matrix':matrix,'process':rows,'new_stages':54,'reused_stages':42,'material_blocks':2,'maximum_arithmetic_error':error,
        'production_changed':False,'main_campaign_paused':False,'scientific_stop':comparison['scientific_stop'],'historical_comparison':comparison}
    s.base.original(work/'analysis.json',result);s.base.original(work/'audit.json',{'passed':True,'complete_states':states,'new_inputs':inputs,
        'new_stages':54,'reused_stages':42,'maximum_arithmetic_error':error,'apparatus':h.read(work/'apparatus.json'),'scientific_stop':comparison['scientific_stop'],'Core_engines_loaded':0})
    print(json.dumps(matrix),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();analyze(a.work)
