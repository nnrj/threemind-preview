"""Read-only complete calibration curves and pre-publication allocation."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pilot_m2 as m
from m5_confirm_summary import inventory


def build(work):
    a=m.read(work/'analysis-v1.json');rows=[]
    for d in a['dose_results']:
        h=[h for o in d['origins'] for h in o['histories']]
        rows.append({'dose':d['dose'],'qualifying_origins':d['qualifying_origins'],
                     'baseline_correct':sum(x['baseline_correct'] for x in h),'histories':len(h),
                     'first_correct':dict(Counter(x['first_correct_lesson'] for x in h)),
                     'late_correct':dict(Counter(x['late_correct_of_four'] for x in h)),
                     'correct_per_lesson':[sum(x['correct_curve'][j] for x in h) for j in range(16)],
                     'signed_response_range':[min(v for x in h for v in x['signed_margins']),max(v for x in h for v in x['signed_margins'])]})
    scale=[]
    for i in range(8):
        folder=work/'units'/f'o{i}'
        for dose in (.1,.2,.3,.4):
            for history in (0,1):
                p=folder/f'd{dose:.2f}-h{history}-lesson16.json.gz'
                v=json.loads(gzip.decompress(p.read_bytes()))
                scale.append({'origin':i,'dose':dose,'history':history,'time_seconds':v['time_us']/1e6,
                              'nodes':len(v['model']['nodes']),'edges':len(v['model']['edges'])})
    return {'schema':'threemind.relearning-assay-summary/1','rows':rows,'scale':scale,
            'verdict':a['verdict'],'selected_lesson_dose':a['selected_lesson_dose'],
            'scientific_savings_tested':False,'first_correct_17_means':'Not reached in 16 lessons; not an observed seventeenth lesson.'}


def figure(summary,path):
    if path.exists():raise FileExistsError(path)
    values=np.array([r['correct_per_lesson'] for r in summary['rows']])/16
    fig,ax=plt.subplots(figsize=(11,4),constrained_layout=True)
    im=ax.imshow(values,vmin=0,vmax=1,cmap='Blues',aspect='auto')
    ax.set_xticks(range(16),range(1,17));ax.set_yticks(range(4),[f"{r['dose']:.2f}" for r in summary['rows']])
    for i,row in enumerate(summary['rows']):
        for j,c in enumerate(row['correct_per_lesson']):ax.text(j,i,f'{c}/16',ha='center',va='center',fontsize=8,color='white' if c>=9 else 'black')
    ax.set_xlabel('Continuous lesson number');ax.set_ylabel('Teaching dose per channel')
    ax.set_title('M2 naive acquisition assay | 8 origins × 2 histories per dose | fixed 110 ms endpoint')
    fig.colorbar(im,ax=ax,label='Correct history fraction');fig.savefig(path,dpi=160);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);work=p.parse_args().work
    assert m.read(work/'audit-v1.json')['passed']
    summary=build(work);m.original(work/'summary-v1.json',summary);figure(summary,work/'figure-v1.png')
    disk=inventory(work);m.original(work/'storage-inventory-v1.json',disk)
    print(json.dumps({'summary_rows':summary['rows'],'scale_values':{k:sorted(set(r[k] for r in summary['scale'])) for k in ('time_seconds','nodes','edges')},'storage':disk}))
