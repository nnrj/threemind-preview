"""Summarize completed E56 stages; never simulates or modifies evidence."""
import json
from collections import defaultdict
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import new_json,read_json
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/vision-correction-20261006'


def paired(a,b):
    if len(a)!=len(b):raise ValueError('paired sizes')
    for x,y in zip(a,b):
        if any(x[k]!=y[k] for k in ('text','items','slot','variant','start')):raise ValueError('paired scene mismatch')
    return {'n':len(a),'a_correct':sum(r['correct'] for r in a),'b_correct':sum(r['correct'] for r in b),
          'wrong_to_right':sum(not x['correct'] and y['correct'] for x,y in zip(a,b)),
          'right_to_wrong':sum(x['correct'] and not y['correct'] for x,y in zip(a,b)),
          'selection_changed':sum(x['selected']!=y['selected'] for x,y in zip(a,b))}


def main():
    results={p.parent.name:read_json(p) for p in sorted((WORK/'cases').glob('*/result.json'))}
    stopped={p.parent.name:read_json(p) for p in sorted((WORK/'cases').glob('*/stopped.json'))}
    pairs={}
    for n in (4,6):
        for a,b in (('teach','corrected'),('teach','exposure'),('exposure','corrected')):
            ap=WORK/f'cases/r{n}-{a}-test-normal/predictions.json';bp=WORK/f'cases/r{n}-{b}-test-normal/predictions.json'
            if not(ap.exists() and bp.exists()):continue
            aa,bb=read_json(ap),read_json(bp)
            pairs[f'r{n}:{a}->{b}']={cat:paired([r for r in aa if r['category']==cat],[r for r in bb if r['category']==cat]) for cat in ('color','shape','pair')}
    a=WORK/'cases/r4-teach-test-normal/predictions.json';b=WORK/'cases/r6-teach-test-normal/predictions.json'
    if a.exists() and b.exists():
        aa,bb=read_json(a),read_json(b)
        pairs['initial:4x4->6x6']={cat:paired([r for r in aa if r['category']==cat],[r for r in bb if r['category']==cat]) for cat in ('color','shape','pair')}
    reference=WORK/'cases/r4-exposure-shared-confirmation-normal/predictions.json'
    activity={}
    if reference.exists():
        normal=read_json(reference)
        for key in ('r4-exposure-shared-confirmation-silence','r4-exposure-shared-confirmation-rescue',
                    'r4-nolearning-exposure-shared-confirmation-normal','r4-corrected-shared-confirmation-normal',
                    'r4-corrected-shared-confirmation-normal-reader-exposure-world-exposure'):
            path=WORK/'cases'/key/'predictions.json'
            if path.exists():
                rows=read_json(path)
                pairs['confirmation:normal->'+key]={cat:paired([r for r in normal if r['category']==cat],
                    [r for r in rows if r['category']==cat]) for cat in ('color','shape','pair')}
        for path in sorted((WORK/'cases').glob('*-shared-confirmation-*/features.npz')):
            if not (path.parent/'result.json').exists():continue
            with np.load(path) as data:
                x=data['x'].reshape(len(data['x']),data['x'].shape[1],-1,4)
                # Raw means, never an input transform or a replacement answer.
                activity[path.parent.name]={field:float(x[:,:,:,i].mean()) for i,field in
                    enumerate(('activation','inhibition','direct','associative'))}
    choices={}
    choice_paths=[*(WORK/'cases').glob('*-test-normal/predictions.json'),
                  *(WORK/'cases').glob('*-shared-confirmation-*/predictions.json')]
    for path in sorted(choice_paths):
        groups=defaultdict(list)
        for row in read_json(path):groups[(row['category'],row['scene'])].append(row)
        choices[path.parent.name]=[{'category':cat,'scene':scene,'choices':[r['selected'] for r in rows],
            'distinct_choices':len({r['selected'] for r in rows}),'correct':sum(r['correct'] for r in rows)}
            for (cat,scene),rows in groups.items()]
    summary={'completed':len(results),'compute_minutes':sum(r['wall_seconds'] for r in (*results.values(),*stopped.values()))/60,
          'stopped':stopped,
          'instances':read_json(WORK/'instances.json')['created'],'stages':results,'paired_comparisons':pairs,
          'raw_confirmation_field_means':activity,
          'same_scene_changed_question':choices,
          'incomplete':[str(p.parent.relative_to(WORK)) for p in (WORK/'cases').glob('*/started.json') if not (p.parent/'result.json').exists()]}
    new_json(HERE/'results.json',summary)
    print(json.dumps({k:summary[k] for k in ('completed','compute_minutes','instances','incomplete')},ensure_ascii=False))

if __name__=='__main__':main()
