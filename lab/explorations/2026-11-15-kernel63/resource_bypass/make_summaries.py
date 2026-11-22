"""Export small tracked summaries; keep complete trajectories in data storage."""
import argparse
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def write(name,value):
    p=HERE/name;assert not p.exists()
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def export(work):
    read=lambda name:json.loads((work/name).read_text('utf8'))
    analysis=read('analysis-final.json');assert analysis['passed']
    summary={k:v for k,v in analysis.items() if k not in ('rows','parents','groups')}
    summary['groups']=[{k:v for k,v in q.items() if not k.endswith('_rows')} for q in analysis['groups']]
    summary['registration']=read('registration.json')
    summary['engineering']=read('engineering/summary.json')
    summary['descriptive']=read('descriptive-analysis.json')
    write('summary.json',summary)
    perf=read('engineering/performance.json')
    write('performance-summary.json',{k:v for k,v in perf.items() if k!='trials'})
    configs={}
    for q in read('phase-A.json'):
        key=q['profile']+'/'+q['variant']
        if key in configs:assert configs[key]==q['patch']
        else:configs[key]=q['patch']
    write('configurations.json',configs)
    p=HERE/'scores.csv';assert not p.exists()
    fields=['profile','variant','group','block','cue','passed','margin','minimum','maximum','end','continuous','saturation_fraction']
    with p.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for q in analysis['rows']:
            if 'process' not in q:continue
            row=q|q['process'];writer.writerow({k:row.get(k,'') for k in fields})
    print(json.dumps({'exported':4,'score_rows':analysis['processes']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);export(p.parse_args().work)
