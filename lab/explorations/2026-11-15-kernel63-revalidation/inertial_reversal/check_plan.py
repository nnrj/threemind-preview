"""Read-only protocol/material checks. No engine is constructed."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(HERE),str(ROOT/'src'),str(ROOT/'lab/explorations/2026-09-30-memory-transfer')]
import spec
import materials
from threemind_kernels.registry import resolve_kernel

def canonical(frames):
    rows=[(int(r['stimulus']['time_us']),tuple(tuple(x) for x in r['stimulus']['channels']),r['stimulus']['intensity']) for r in frames]
    return sorted(rows)

def check_revalidation_inputs(historical,reference):
    teaching={x['key']:x for x in spec.load(reference/'body-memory-cases.json')}
    transfer={x['key']:x for x in spec.load(reference/'body-transfer-cases.json')}
    checked=0
    for subject in spec.subjects(.018):
        if subject['variant']!='v63-prequeue':continue
        prefix=f"{subject['seed']}-{subject['preset']}-{subject['mode']}"
        for stage in spec.stages(subject):
            rows=spec.inputs(historical,subject,stage,materials.identities(subject['seed']))
            if stage['name'] in ('teaching','wait1'):
                previous=teaching[prefix+'-'+stage['name']]
            else:
                suffix='-none-0' if stage['sign']==0 else '-original-'+str(stage['sign'])
                previous=transfer['transfer-'+prefix+suffix]
                assert previous['targets']==[materials.identities(subject['seed'])[k] for k in ('A','B')]
            assert [x['stimulus'] for x in rows]==[x['stimulus'] for x in previous['inputs']]
            checked+=1
    assert checked==80
    return checked

def check(historical,reference=None):
    subjects=spec.subjects(.018);stages=0;frames=0
    assert len(subjects)==320 and len({s['key'] for s in subjects})==320
    for subj in subjects:
        config=resolve_kernel(subj['kernel']).configuration(subj['config'])
        assert config.seed==subj['seed']
        mappings=materials.identities(subj['seed'])
        for stage in spec.stages(subj):
            rows=spec.inputs(historical,subj,stage,mappings)
            frames+=len(rows);stages+=1
            if subj['queue_policy']=='prequeue':
                streamed=spec.inputs(historical,dict(subj,queue_policy='stream'),stage,mappings)
                assert canonical(rows)==canonical(streamed)
            if stage['name']=='teaching' and subj['kernel'].endswith('/2') and subj['variant']=='v2':
                old=spec.load(spec.physical_folder(historical,subj,stage)/'result.json')['config']
                actual=config.to_dict()
                assert all(actual[k]==v for k,v in old.items()),{k:(v,actual.get(k)) for k,v in old.items() if actual.get(k)!=v}
    assert stages==1792
    initial_min=.065*.5
    rate=.1*.025*(1-(.08+.92*0))
    floor=initial_min*(1-rate)**(25.8/.1)
    assert floor>.008 and 25.8<80
    return {'passed':True,'subjects':len(subjects),'stages':stages,'initial_final_states':stages*2,
        'prequeue_sequences_equal_to_R63c_h':check_revalidation_inputs(historical,reference) if reference else None,
        'formal_material_blocks':4,'input_frame_records_checked':frames,'queue_values_and_arrival_times_identical':True,
        'historical_recorded_config_equal':True,'Core_engines_loaded':0,
        'historical_deletion_bound':{'minimum_birth_weight':initial_min,'max_pulse_loss':rate,'duration_s':25.8,
            'weight_lower_bound':floor,'prune_weight':.008,'node_min_inactivity_s':80,
            'premise':'E18 defaults, nonnegative reinforcement, no energy damage or declared disconnection',
            'sources':['src/threemind_core/restoration.py','src/threemind_kernels/continuous.py']}}

if __name__=='__main__':
    print(json.dumps(check(ROOT/'.work/memory-transfer-20260930/cases'),indent=2))
