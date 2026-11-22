"""Post-run descriptive waiting-course and cost summaries; does not change scores."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t16_extra_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

def analyze(work):
    assert t.s.read(work/'phase-A-summary.json')['stages']==72
    output=work/'descriptive-analysis.json';assert not output.exists()
    rows=[]
    for stage in t.s.read(work/'phase-A.json'):
        if stage['group']!='persistent' or stage['cue']!='wait':continue
        values=[];times=[];targets={v^stage['mask'] for v in t.s.measure.TOKENS.values()}
        with gzip.open(work/'cases'/stage['key']/'course.jsonl.gz','rt',encoding='utf8') as stream:
            for line in stream:
                frame=json.loads(line);times.append(frame['time_us'])
                values.append(max((n['activation'] for n in frame['nodes'] if n['channel'] in targets),default=0))
        rows.append({'key':stage['key'],'samples':len(times),'begin_us':times[0],'end_us':times[-1],
            'maximum_sample_gap_us':max(b-a for a,b in zip(times,times[1:])),
            'minimum_task_activation_maximum':min(values),'maximum_task_activation_maximum':max(values),
            'samples_above_1e_6':sum(v>1e-6 for v in values),
            'first_inactive_us':next((when for when,v in zip(times,values) if v<=1e-6),None)})
    perf=t.s.read(work/'engineering/performance.json');ratios=[]
    for n in (32,128):
        for distribution in ('per-connection','weight-proportional'):
            on=next(q for q in perf['results'] if q['nodes']==n and q['distribution']==distribution and q['bypass'])
            off=next(q for q in perf['results'] if q['nodes']==n and q['distribution']==distribution and not q['bypass'])
            a,b=on['first']['current']['wall_seconds'],off['first']['current']['wall_seconds']
            ratios.append({'nodes':n,'distribution':distribution,'bypass_on_seconds':a,
                'bypass_off_seconds':b,'ratio':a/b,'interpretation':'different dynamics; not optional-code overhead'})
    t.s.write(output,{'analysis_identity':'post-run descriptive analysis; registered scores unchanged',
        'waiting_course':rows,'bypass_cost_comparison':ratios})
    print(json.dumps(t.s.read(output)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);analyze(p.parse_args().work)
