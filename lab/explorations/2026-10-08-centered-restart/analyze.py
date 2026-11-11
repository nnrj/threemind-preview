"""Summarize actual answers without stepping or fitting anything."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import read_json,new_json
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/centered-restart-20261008'


def main():
    cases={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/result.json')}
    failures={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/stopped.json')}
    result=dict(schema='threemind.centered-restart-results/1',cases=cases,failures=failures,
        compute_minutes=(sum(v['wall_seconds'] for v in cases.values())+
                         sum(v['wall_seconds'] for k,v in failures.items() if k not in cases))/60,
        instances=read_json(WORK/'instances.json'),answers={},paired={})
    predictions={}
    for name in ('test-normal','confirmation-normal','test-silence','test-rescue'):
        if name not in cases:continue
        rows=read_json(WORK/'cases'/name/'predictions.json');predictions[name]=rows
        conf=[[0]*8 for _ in range(8)]
        for row in rows:
            if row['correct']!=(row['label']==row['selected']):raise ValueError('answer/scoring discrepancy')
            conf[row['label']][row['selected']]+=1
        covered=[r for r in rows if r['conjunction_calibrated']]
        novel=[r for r in rows if not r['conjunction_calibrated']]
        result['answers'][name]=dict(n=len(rows),correct=sum(r['correct'] for r in rows),
            shape_correct=sum(r['correct'] for r in rows if r['label']<4),
            color_correct=sum(r['correct'] for r in rows if r['label']>=4),
            calibrated_type=dict(n=len(covered),correct=sum(r['correct'] for r in covered)),
            uncalibrated_type=dict(n=len(novel),correct=sum(r['correct'] for r in novel)),confusion=conf,
            wrong=[r for r in rows if not r['correct']])
    if 'test-normal' in predictions:
        normal={r['question_id']:r for r in predictions['test-normal']}
        for mode in ('silence','rescue'):
            name='test-'+mode
            if name not in predictions:continue
            rows=predictions[name]
            result['paired'][mode]=dict(n=len(rows),changed=sum(r['selected']!=normal[r['question_id']]['selected'] for r in rows),
                correct_to_wrong=sum(normal[r['question_id']]['correct'] and not r['correct'] for r in rows),
                wrong_to_correct=sum(not normal[r['question_id']]['correct'] and r['correct'] for r in rows))
    result['blank_passed']=all(cases.get(sp+'-normal',{}).get('reliable',False) for sp in ('test','confirmation'))
    new_json(HERE/'results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','answers','failures')},ensure_ascii=False))
    for key,ans in result['answers'].items():print(json.dumps(dict(case=key,**{k:v for k,v in ans.items() if k not in ('confusion','wrong')}),ensure_ascii=False))


if __name__=='__main__':main()
