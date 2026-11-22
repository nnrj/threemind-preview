"""Read-only replication check against R51t14's shared and independent controls."""
import argparse
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t15_prior_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s
def audit(work):
    old=work.parent/'resources63-v1';rows=[]
    assert s.read(old/'publication/completion.json')['pending']==0
    for q in s.read(old/'phase-A.json'):
        if q['profile']!='S' or q['patch']['inhibition_distribution']!='weight-proportional':continue
        independent=q['patch']['separate_inhibition_resources']
        name=('independent' if independent else 'shared')+'-l1-g1'
        key=f"B/S/{name}/{q['block']}/{q['cue']}"
        previous=old/'cases'/q['key'];current=work/'cases'/key
        a=s.read(previous/'result.json');b=s.read(current/'result.json')
        left=t.h.get(previous/'final.rstate.gz');right=t.h.get(current/'final.rstate.gz')
        assert left.digest==a['final_sha256'] and right.digest==b['final_sha256']
        old_config=left.to_dict()['config'];new_config=right.to_dict()['config']
        new_config={k:v for k,v in new_config.items() if not k.startswith('research_')}
        assert old_config==new_config
        assert s.unpack(previous/'inputs.json.gz')==s.unpack(current/'inputs.json.gz')
        errors={k:abs(v-b['process'][k]) for k,v in (a['process'] or {}).items() if isinstance(v,(int,float))}
        assert max(errors.values(),default=0)<1e-12,errors
        rows.append({'key':key,'original':q['key'],'old_state_sha256':left.digest,
            'new_state_sha256':right.digest,'configuration_and_inputs_equal':True,
            'max_process_error':max(errors.values(),default=0)})
    assert len(rows)==12
    result={'passed':True,'rows':rows,'max_process_error':max(x['max_process_error'] for x in rows)}
    s.write(work/'prior-baseline-audit.json',result)
    print(json.dumps({'passed':True,'comparisons':len(rows),'max_process_error':result['max_process_error']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
