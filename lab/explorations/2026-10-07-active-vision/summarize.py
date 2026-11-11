"""Summarize this study's bounded evidence; no simulation or old data audit."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lab.tools.service_study import read_json,new_json

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/active-vision-20261007'


def main():
    cases={p.parent.name:read_json(p) for p in sorted((WORK/'cases').glob('*/result.json'))}
    stopped={p.parent.name:read_json(p) for p in sorted((WORK/'cases').glob('*/stopped.json'))}
    growth={k:{**v['metrics'][-1],'peak_rss_bytes':v['peak_rss_bytes'],'mean_incoming':v['input_mean']}
            for k,v in cases.items() if k.startswith('A-')}
    observations={}
    for p in WORK.glob('gaze-*.json'):
        rows=read_json(p)['segments'];metrics=[r['metrics'] for r in rows]
        observations[p.stem]={'segments':len(rows)}
        for key in ('association_integral','direct_integral','mean_activation','mean_eye_speed_rad_s',
                    'mean_gaze_hand_distance_m','target_central_fraction','target_in_field_fraction'):
            numbers=[r[key] for r in metrics if r[key] is not None]
            observations[p.stem][key+'_mean']=float(np.mean(numbers)) if numbers else None
    comparisons={}
    for key,value in cases.items():
        if key.startswith('C-') and value['mode']=='normal':
            path=WORK/'cases'/key/'predictions.json';normal=read_json(path)
            for mode in ('empty','silence','rescue'):
                other=WORK/'cases'/key.replace('-normal','-'+mode)/'predictions.json'
                if not other.exists():continue
                rows=read_json(other)
                if len(normal)!=len(rows):raise ValueError('paired comparison length')
                comparisons[key+' versus '+mode]={'n':len(rows),
                    'choice_changed':sum(a['chosen']!=b['chosen'] for a,b in zip(normal,rows)),
                    'endpoint_changed':sum(not np.allclose(a['actual'],b['actual'],atol=1e-9,rtol=0) for a,b in zip(normal,rows)),
                    'normal_correct':sum(r['correct'] for r in normal),'other_correct':sum(r['correct'] for r in rows)}
    result={'study':'E59 active vision','cases':cases,'stopped':stopped,'growth':growth,'gaze_observations':observations,
            'teaching_audit':read_json(WORK/'teaching-audit.json'),
            'frozen_sequence_selection':read_json(WORK/'sequence-selection-scan.json'),
            'optical_projection':read_json(WORK/'optical-projection.json'),
            'paired_controls':comparisons,'created_instances':read_json(WORK/'instances.json')['created'],
            'compute_minutes':sum(v['wall_seconds'] for v in [*cases.values(),*stopped.values()])/60,
            'local_bytes_before_archive':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
            'core_changed':False,'independent_core_seed_count':1,
            'sampling_unit':'questions/layouts and branches of one configured seed; not independent brains'}
    new_json(HERE/'results.json',result)
    names=list(growth);fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    for ax,field,title in zip(axes,('edges','elapsed_wall'),('Edges after 10 simulated seconds','Elapsed compute seconds')):
        values=[growth[k][field] for k in names];bars=ax.bar([k[2:] for k in names],values,color=['#5a8478','#a36c58','#389b83','#137c65','#7aae9f'])
        ax.bar_label(bars,labels=[f'{v:,.0f}' if field=='edges' else f'{v:.1f}' for v in values],padding=3,fontsize=9)
        ax.set_title(title);ax.spines[['top','right']].set_visible(False);ax.tick_params(axis='x',labelrotation=18);ax.set_ylim(0,max(values)*1.15)
    fig.suptitle('E59: complete scene, fixed receptor budget; Core unchanged');fig.tight_layout();fig.savefig(HERE/'summary.png',dpi=160)
    print(json.dumps({k:result[k] for k in ('created_instances','compute_minutes','local_bytes_before_archive')}))


if __name__=='__main__':main()
