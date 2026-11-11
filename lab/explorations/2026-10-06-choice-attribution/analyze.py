"""Summarize every completed E57 condition; never select the best seed."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import read_json,new_json
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/choice-attribution-20261006'


def summarize():
    cases={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/result.json')}
    a=[];b=[];correction=[];controls=[];dose=[];absent=[];sensitivity=[];marker=[]
    for key,row in sorted(cases.items()):
        value={'case':key}|row
        if key.startswith('A-') and 'correct' in row:a.append(value)
        elif key.endswith('frozen-correction'):correction.append(value)
        elif key.startswith('B-') and key.endswith('-fit'):b.append(value)
        elif key.startswith('B-') and '-control-score-' in key:controls.append(value)
        elif key.startswith('D-'):dose.append(value)
        elif key=='C-absent-activity':absent.append(value)
        elif key.startswith('E-'):sensitivity.append(value)
        elif key.startswith('F-') and '-score-' in key:marker.append(value)
    intervention_details=[]
    for row in [*controls,*marker]:
        key=row['case'];seed=row['seed']
        original=read_json(WORK/f'cases/B-s{seed}-learned-fit/predictions.json')
        current=read_json(WORK/'cases'/key/'predictions.json')
        base=np.asarray(original['predictions']);pred=np.asarray(current['predictions'])
        truth=np.asarray(current['targets'])
        if not np.array_equal(truth,original['targets']):raise ValueError('unaligned intervention targets')
        intervention_details.append({'case':key,'own_history_correct':int((pred==truth).sum()),
            'opposite_history_correct':int((pred==truth[::-1]).sum()),
            'changed_from_baseline':int((pred!=base).sum()),
            'lost_correct':int(((base==truth)&(pred!=truth)).sum()),
            'gained_correct':int(((base!=truth)&(pred==truth)).sum()),
            'exact_opposite_history_predictions':int((pred==base[::-1]).sum())})
    dose_totals=[]
    for steps in (100,300,1200):
        for mode in ('learned','unlearned','incoming'):
            rows=[r for r in dose if r['steps']==steps and r['mode']==mode]
            if not rows:continue
            value={'steps':steps,'mode':mode,'seed_correct':[r['correct'] for r in rows],
                   'correct':sum(r['correct'] for r in rows),'n':sum(r['n'] for r in rows),
                   'scope':'repeated external training on the same 24 tasks, not independent worlds'}
            if mode=='learned':
                for condition in ('silence','rescue'):
                    value[condition]={field:sum(r[condition][field] for r in rows)
                        for field in ('correct','changed','lost_correct','gained_correct')}
            dose_totals.append(value)
    mask_quality=[{'source':p.stem,**{k:v for k,v in read_json(p).items() if k not in ('target','matched')}}
                  for p in sorted(WORK.glob('masks-*.json'))]
    differences=[]
    for seed in (223,279):
        for p in (0,1):
            paths=[WORK/f'cases/B-s{seed}-p{p}-h{h}-teach-test-normal/features.npz' for h in (0,1)]
            if not all(path.exists() for path in paths):continue
            arrays=[np.load(path) for path in paths]
            # Descriptive differences only. Never feed subtracted signals to readers.
            delta=np.abs(arrays[0]['activity']-arrays[1]['activity']).reshape(16,8,-1,4)
            differences.append({'seed':seed,'plasticity':bool(p),
                'different_activity_pairs':int(np.any(delta>0,axis=(1,2,3)).sum()),
                'mean_absolute_difference':dict(zip(('activation','inhibition','direct','associative'),map(float,delta.mean(axis=(0,1,2)))))})
    return {'schema':'threemind.choice-attribution-results/1','stage_A':a,'stage_B':b,
            'frozen_reader_correction':correction,'pathway_controls':controls,
            'external_practice_dose':dose,'absent_activity':absent,
            'reader_sensitivity':sensitivity,'marker_state_interventions':marker,
            'intervention_prediction_changes':intervention_details,'dose_totals':dose_totals,
            'matched_edge_control_quality':mask_quality,
            'descriptive_history_differences':differences,
            'completed_cases':len(cases),'created':read_json(WORK/'instances.json')['created'],
            'wall_seconds':sum(r['wall_seconds'] for r in cases.values()),
            'local_bytes_before_archive':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
            'partial_cases':[p.name for p in (WORK/'cases').iterdir() if p.is_dir() and not (p/'result.json').exists()],
            'independence':'A seeds share E56 data. B sources share sensory mapping/curriculum, but source279 changes weather47->103, as amended before its execution. Core seed alone is inert without the optional spatial substrate. Forks are paired, not independent animals.'}


if __name__=='__main__':
    result=summarize()
    if '--save' in sys.argv:new_json(HERE/'results.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
