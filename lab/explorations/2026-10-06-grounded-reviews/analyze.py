"""Paired question/action analysis of completed E55 evidence; no new simulation."""
import json
import gzip
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/grounded-reviews-20261006'


def read(path):return json.loads(path.read_bytes())


def comparison(a,b,correct='correct',prediction='prediction'):
    if len(a)!=len(b):raise ValueError('paired count')
    return {'n':len(a),'both_correct':sum(x[correct] and y[correct] for x,y in zip(a,b)),
      'a_only_correct':sum(x[correct] and not y[correct] for x,y in zip(a,b)),
      'b_only_correct':sum(not x[correct] and y[correct] for x,y in zip(a,b)),
      'both_wrong':sum(not x[correct] and not y[correct] for x,y in zip(a,b)),
      'prediction_changed':sum(x[prediction]!=y[prediction] for x,y in zip(a,b))}


def main():
    result={'schema':'threemind.grounded-classroom-analysis/1','questions':{},'actions':{}}
    for p in sorted((WORK/'cases').glob('*-expression/predictions.json')):
        key=p.parent.name.removesuffix('-expression');rows=read(p)
        result['questions'][key]={}
        for split in ('familiar','held'):
            data=[r for r in rows if r['split']==split]
            result['questions'][key][split]={
                'views':{str(v):{'n':sum(r['variant']==v for r in data),
                            'correct':sum(r['correct'] for r in data if r['variant']==v)} for v in sorted({r['variant'] for r in data})},
                'by_target':{str(t):{'n':sum(r['target']==t for r in data),
                              'correct':sum(r['correct'] for r in data if r['target']==t)} for t in range(8)}}
        silence=WORK/f'cases/{key}-familiar-silence-score/predictions.json'
        if silence.exists():
            normal=[r for r in rows if r['split']=='familiar']
            result['questions'][key]['normal_vs_silence']=comparison(normal,read(silence))
    base=WORK/'cases/s223-motor-test-episode-normal/trials.json'
    if base.exists():
        normal=read(base)
        for path in sorted((WORK/'cases').glob('s223-motor-test-*/trials.json')):
            if not (path.parent/'result.json').exists():continue
            rows=read(path);key=path.parent.name
            result['actions'][key]={'paired_to_episode_normal':comparison(normal[:len(rows)],rows,'choice_correct','chosen'),
                'by_view':{str(v):{'n':sum(r['variant']==v for r in rows),
                         'choice_correct':sum(r['choice_correct'] for r in rows if r['variant']==v),
                         'reached':sum(r['reached'] for r in rows if r['variant']==v)} for v in sorted({r['variant'] for r in rows})},
                'endpoint_change_median':float(np.median([np.linalg.norm(np.array([r['final_pointer'][k] for k in ('x','y')])-
                         [b['final_pointer'][k] for k in ('x','y')]) for r,b in zip(rows,normal)]))}
            # Request reversal can change which pair is held out. Use the
            # actually requested object, not the original question's flag.
            for held in (False,True):
                selected=[r for r in rows if (r['items'][r['requested_slot']][0]==r['items'][r['requested_slot']][1])==held]
                result['actions'][key]['requested_held' if held else 'requested_taught']={
                    'n':len(selected),'choice_correct':sum(r['choice_correct'] for r in selected),
                    'reached':sum(r['reached'] for r in selected)}
            # Descriptive kinematics, not additional success criteria. All
            # targets here are observer-only scoring information.
            progress={str(t):[] for t in (.25,1.,2.)}
            with gzip.open(path.parent/'process.jsonl.gz','rt',encoding='utf-8') as stream:
                for line in stream:
                    record=json.loads(line);trial=record['trial']
                    action=[r for r in record['process'] if 'pointer_after' in r]
                    target=np.array(((-.55,-.55),(.55,-.55),(-.55,.55),(.55,.55)))[trial['requested_slot']]
                    initial=np.linalg.norm(target-[action[0]['observation']['pointer'][k] for k in ('x','y')])
                    for t in (.25,1.,2.):
                        frame=action[round(t/.05)-1]['pointer_after']
                        progress[str(t)].append(float(initial-np.linalg.norm(target-[frame[k] for k in ('x','y')])))
            result['actions'][key]['distance_progress']={t:{'closer':sum(v>0 for v in values),
                'median_metres':float(np.median(values)),'n':len(values)} for t,values in progress.items()}
    (HERE/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
