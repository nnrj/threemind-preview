"""Verify old-scale controls and the registered posture criterion without a world or Core."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import body_analysis as a
h=a.h


def verify():
    cases=h.table();assert cases==h.read(h.HISTORY/'cases.json')
    assert len(cases)==296 and sum(c['kind']=='static' for c in cases)==120
    oldfile=h.ROOT/'lab/explorations/2026-11-13-kernel61/dynamics_function/body.py'
    functions=lambda p:{f.name:ast.dump(f,include_attributes=False) for f in ast.parse(p.read_text('utf-8')).body if isinstance(f,ast.FunctionDef)}
    old,new=functions(oldfile),functions(HERE/'body.py')
    for name in ('table','mapping','sensory','world_spec','integral','frame_nodes'):assert old[name]==new[name]
    seed=h.SEEDS[0];mask=h.channel_id(seed,'world-port-v1:physical-world-v1',0)
    imu=(1<<20)^mask;joint=(2<<20)^mask
    sample={'elements':[{'channel':imu,'value':2.},{'channel':joint,'value':2.}],'time_us':'0','intensity':.3}
    matched=h.sensory(sample,'dose_matched',seed,random.Random(1))
    assert {v['channel']:v['value'] for v in matched['elements']}=={imu:1.,joint:1.}
    removed=h.sensory(sample,'no_imu',seed,random.Random(1))
    assert removed['elements']==[{'channel':joint,'value':2.}]
    oldresult=h.read(h.HISTORY/'analysis.json');decision=a.functional_decision(oldresult['contrasts'])
    assert not decision['passed']
    synthetic=deepcopy(oldresult['contrasts'])
    for row in synthetic:
        if row['mode']=='full':row['relative_improvement_high_threshold']['angle_rms']=.11 if row['polarity']==1 else -.09
    assert a.functional_decision(synthetic)['passed']
    for row in synthetic:
        if row['mode']=='full' and row['polarity']==-1:row['relative_improvement_high_threshold']['angle_rms']=-.11
    assert not a.functional_decision(synthetic)['passed']
    error=0.;count=0
    for c in cases:
        if c['kind']=='body' and c['seed']==h.SEEDS[0] and c['mode']=='full' and c['sign']==1:
            points=h.e.unpacked(h.HISTORY/'cases'/c['key']/'trajectory.json.xz')
            physical=[p for p in points if 'q' in p]
            rms=math.sqrt(math.fsum(p['q']**2 for p in physical[:-1])/400)
            recorded=next(r['angle_rms'] for r in oldresult['body'] if r['key']==c['key'])
            error=max(error,abs(rms-recorded));count+=1
    assert count==6 and error<1e-12
    return {'passed':True,'unchanged_stage_table':296,'static_stages':120,'body_stages':176,
        'dose_matching_retains_inertial_channels':True,'opposite_wiring_harm_rejected':True,
        'original_functional_negative_reproduced':True,'recomputed_body_trajectories':count,'maximum_rms_error':error}


if __name__=='__main__':print(json.dumps(verify()))
