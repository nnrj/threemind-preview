"""Compare the new positive witnesses with immutable R51t11 originals."""
from copy import deepcopy
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t15_historical_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s

def numerical(image):
    d=deepcopy(image.to_dict())
    for k in ('schema','dynamics','definition','definition_hash','config','audit'):d.pop(k,None)
    return d

def verify(work):
    old_plan={x['key']:x for x in s.read(t.OLD/'phase-E.json')}
    rows=[]
    for stage in s.read(work/'phase-A.json'):
        if stage['variant']=='usage-on':continue
        old_key=f"E/normalized-path/{stage['block']}/{stage['cue']}"
        original=t.OLD/'cases'/old_key;current=work/'cases'/stage['key']
        old_result=s.read(original/'result.json');new_result=s.read(current/'result.json')
        assert stage['case']==old_plan[old_key]['case']
        assert s.unpack(original/'inputs.json.gz')==s.unpack(current/'inputs.json.gz')
        old_image=t.h.get(original/'final.rstate.gz');new_image=t.h.get(current/'final.rstate.gz')
        assert old_image.digest==old_result['final_sha256'] and new_image.digest==new_result['final_sha256']
        old_cfg,new_cfg=old_image.to_dict()['config'],new_image.to_dict()['config']
        # These are renamed or additional research controls; all common physical parameters must match.
        config_changes={k:[old_cfg.get(k),new_cfg.get(k)] for k in old_cfg.keys()|new_cfg.keys()
                        if old_cfg.get(k)!=new_cfg.get(k)}
        allowed={'inhibition_distribution','inhibition_updates_usage','separate_inhibition_resources',
                 'research_inhibition_marks_usage','research_normalize_inhibition',
                 'research_legacy_emission','research_learning_component'}
        assert not (config_changes.keys()-allowed),config_changes
        errors={k:abs(v-new_result['process'][k]) for k,v in (old_result['process'] or {}).items()
                if isinstance(v,(int,float))}
        if stage['variant']=='legacy-positive':assert max(errors.values(),default=0)<1e-10,errors
        a,b=numerical(old_image),numerical(new_image)
        rows.append({'key':stage['key'],'original':old_key,'old_state_sha256':old_image.digest,
            'new_state_sha256':new_image.digest,'equal_inputs':True,'config_changes':config_changes,
            'numerical_state_equal':a==b,'different_state_fields':[k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)],
            'process_max_error':max(errors.values(),default=0),
            'old_process':old_result['process'],'new_process':new_result['process'],
            'old_audit':old_image.to_dict()['audit'],'new_audit':new_image.to_dict()['audit']})
    assert len(rows)==12
    return {'passed':True,'rows':rows,'old_receipt_sha256':s.sha(t.OLD/'publication/completion.json')}

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    result=verify(a.work);s.write(a.work/'historical-comparison.json',result)
    print(json.dumps({'passed':True,'comparisons':len(result['rows']),
        'numerically_equal':sum(x['numerical_state_equal'] for x in result['rows']),
        'max_score_error':max(x['process_max_error'] for x in result['rows'])}))
