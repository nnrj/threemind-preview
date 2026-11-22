"""Read historical evidence and exercise both positive and negative decision cases."""
import copy
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism_analysis as a


def verify():
    cases=a.h.design.cases(a.h.previous.design.cases())
    original=a.h.read(a.h.HISTORY/'cases.json')
    for row,old in zip(cases,original):
        inverse={k:v for k,v in row.items() if k not in ('historical_case','historical_case_file','design_part')}
        for field in ('key','parent','variant'):
            if isinstance(inverse[field],str):inverse[field]=inverse[field].replace('v63','v61')
        inverse['version']='6.1'
        assert inverse==old
    evidence=a.h.read(a.h.HISTORY/'analysis.json');rows=evidence['process'];waits={}
    for v in evidence['variants']:
        if v['group']=='persistent':
            for b in v['blocks']:waits[v['variant']+':'+str(b['block'])]=b['last_positive_seconds']
    summary=a.summarize(rows,waits);assert summary==evidence['variants']
    assert not a.compare(summary)['scientific_stop']
    selection=a.select_candidates(summary,cases)
    assert selection['persistent']['variant']=='persist-g0.24-t0.25'
    assert selection['prefix']['variant']=='prefix-immediate-no-inhibitory-learning'
    positive=next(v for v in summary if v['passed_blocks']==2)
    bad=copy.deepcopy(summary)
    next(v for v in bad if v['variant']==positive['variant'])['passed_blocks']=1
    assert a.compare(bad)['scientific_stop']
    bad=copy.deepcopy(summary)
    next(v for v in bad if v['variant']==positive['variant'])['blocks'][0]['saturation_fraction']=.2
    assert a.compare(bad)['scientific_stop']
    errors=[];recomputed=0
    for c in cases:
        if c['kind']=='probe' and c['block']==0 and c['variant'] in (
            'persist-g0.24-t0.25','prefix-immediate-no-inhibitory-learning'):
            points=a.e.unpacked(a.h.HISTORY/'cases'/c['key']/'trajectory.json.xz')['points']
            row=a.m.process(c,points);reference=next(r for r in rows if r['key']==c['key'])
            assert all(value==reference[key] for key,value in row.items());errors.append(row['arithmetic_error']);recomputed+=1
    assert recomputed==3
    return {'passed':True,'stages':len(cases),'unchanged_historical_case_definitions':True,
        'scored_conditions':len(summary),'recomputed_processes':recomputed,
        'lost_positive_detected':True,'new_saturation_risk_detected':True,'historical_candidates_reproduced':True,
        'maximum_arithmetic_error':max(errors)}


if __name__=='__main__':print(json.dumps(verify()))
