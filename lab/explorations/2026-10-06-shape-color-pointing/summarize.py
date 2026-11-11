"""Summarise completed E54 cases, without simulation or rewriting evidence."""
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/shape-color-20261006'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    cases={}
    incomplete={}
    for folder in sorted((WORK/'cases').iterdir()):
        if not folder.is_dir():continue
        file=folder/'result.json'
        if file.exists():
            r=read(file)
            cases[folder.name]={k:v for k,v in r.items() if k not in ('trials','runner_signature')}
        else:
            file=folder/'failure.json'
            incomplete[folder.name]=read(file) if file.exists() else {'status':'no completed result'}
    paired={}
    normal=WORK/'cases/s223-goal-test-normal/trials.json'
    changed=WORK/'cases/s223-goal-test-wrong-request/trials.json'
    if normal.exists() and changed.exists():
        a,b=read(normal),read(changed)
        assert len(a)==len(b)
        for x,y in zip(a,b):
            assert (x['shape'],x['color'],x['variant'],x['slot'])==(y['shape'],y['color'],y['variant'],y['slot'])
        delta=[float(np.hypot(x['final_pointer']['x']-y['final_pointer']['x'],
                              x['final_pointer']['y']-y['final_pointer']['y'])) for x,y in zip(a,b)]
        # The original 'reached' field intentionally scores the original target,
        # including in changed-request trials. Also report the actually named
        # target using its recorded slot and physical final pointer.
        positions=((-0.55,-0.55),(0.55,-0.55),(-0.55,0.55),(0.55,0.55))
        def requested_reached(row):
            target=positions[row['requested_slot']];p=row['final_pointer']
            return np.hypot(p['x']-target[0],p['y']-target[1])<=0.15
        paired={'n':len(a),'changed_nearest_object':sum(x['chosen']!=y['chosen'] for x,y in zip(a,b)),
                'normal_request_correct':sum(x['requested_choice_correct'] for x in a),
                'changed_request_correct':sum(y['requested_choice_correct'] for y in b),
                'normal_requested_reached':int(sum(requested_reached(x) for x in a)),
                'changed_requested_reached':int(sum(requested_reached(y) for y in b)),
                'both_requests_correct':sum(x['requested_choice_correct'] and y['requested_choice_correct'] for x,y in zip(a,b)),
                'median_endpoint_change_m':float(np.median(delta))}
    result={'schema':'threemind.shape-color-results/1','date':'2026-10-06',
            'project_id':read(WORK/'platform.json')['project_id'],
            'cases':cases,'incomplete_cases':incomplete,'paired_changed_request':paired,
            'sensor_calibration':read(WORK/'sensor-calibration.json') if (WORK/'sensor-calibration.json').exists() else None,
            'resources':{'completed_cases':len(cases),
                         'completed_case_compute_minutes':sum(c['wall_seconds'] for c in cases.values())/60,
                         'created_core_instances':read(WORK/'instances.json')['created'],
                         'usage_start':59,'usage_latest':read(WORK/'usage.json')['used_percent']},
            'unperformed':['second learned source 279','long-term energy selection for motor motivation',
                           'semantic self/other learning','free natural-language dialogue','general logical reasoning'],
            'limitations':['forked trials are not independent learned individuals',
                           'correction retests are exploratory; preserved original scores remain separate',
                           'current heads can learn task mappings externally; raw Core dependence is not learned-edge mediation']}
    path=HERE/'results.json'
    if path.exists():raise RuntimeError('existing summary preserved; create an explicitly dated revision')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['resources'],ensure_ascii=False))


if __name__=='__main__':main()
