"""Observe complete post-teaching histories through frozen native readers."""
from collections import Counter, deque
import gzip
import json
import time
from types import SimpleNamespace

import torch

from experiment import HERE, WORK, SEEDS, encoded, guard, read_json, new_json, study
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import NativeProjection
from threemind_transformer.development_model import load


def windows(path):
    """Four actual half-second chunks, not a half-second history stretched to 2 s."""
    queue=deque(maxlen=4)
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['acquisition']:
                raise ValueError('post-teaching observation unexpectedly contains teaching')
            queue.append(row['process'])
            if len(queue)<4:continue
            frames=[];last=-1
            for chunk in queue:
                for frame in chunk['trajectory']:
                    when=int(frame['time_us'])
                    if when>last:frames.append(frame);last=when
            yield {'start_us':queue[0]['start_us'],'end_us':queue[-1]['end_us'],
                   'planned_end_us':queue[-1]['end_us'],'trajectory':frames}


def run():
    torch.set_num_threads(2);s=study();started=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=started)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    scopes=read_json(WORK/'projection.json')
    domains={'language':set(scopes['vision']['excluded_channels']),
             'vision':set(scopes['words']['excluded_channels'])}
    background=set(scopes['vision']['channels'])-domains['vision']
    # All known non-sensory channels in this protocol belong to the recorded telemetry.
    domains['background']=background
    summary=[];candidates=[]
    try:
        for seed in SEEDS:
            heads={}
            for regime in ('individual','developmental'):
                for modality in ('vision','words'):
                    manifest=read_json(WORK/'models'/f'{regime}-s{seed}-{modality}.json')
                    heads[(regime,modality)]=(load(WORK/'models'/manifest['checkpoint'],device)[0],
                        NativeProjection(**manifest['projection']),FeatureCalibration(**manifest['feature_calibration']))
            for condition,boundary in (('normal',326),('background',532),('frozen',326)):
                source=f's{seed}-{condition}'
                target=WORK/'continuous'/f'{source}.jsonl.gz'
                if target.exists():raise RuntimeError('preserve completed continuous analysis; resume explicitly')
                target.parent.mkdir(exist_ok=True)
                rows=[];previous={k:None for k in domains};declining={k:0 for k in domains};last_time=None
                candidate=None;unique_frames=0
                for process in windows(WORK/'cases'/source/f'process-{boundary}.jsonl.gz'):
                    curves={k:[] for k in (*domains,'all','inhibition')}
                    for frame in process['trajectory']:
                        values={k:sum(n['activation'] for n in frame['nodes'] if int(n['channel']) in channels)
                                for k,channels in domains.items()}
                        values['all']=sum(n['activation'] for n in frame['nodes'])
                        values['inhibition']=sum(n.get('inhibition',0) for n in frame['nodes'])
                        for k,v in values.items():curves[k].append(v)
                        when=int(frame['time_us'])
                        if last_time is not None and when<=last_time:continue
                        elapsed=0 if last_time is None else when-last_time
                        for k in domains:
                            if previous[k] is not None:
                                increased=values[k]>previous[k]+1e-8
                                if (candidate is None and condition!='frozen' and k!='background' and
                                    when>=271000000 and increased and declining[k]>=100000):
                                    candidate={'source':source,'seed':seed,'domain':k,'when_us':when,
                                        'preceding_nonincrease_us':declining[k],
                                        'definition':'sensory activity rises after >=100ms nonincrease, >=5s after teaching; not proof of autonomy'}
                                declining[k]=0 if increased else declining[k]+elapsed
                            previous[k]=values[k]
                        last_time=when;unique_frames+=1
                    rows.append({'start_us':process['start_us'],'end_us':process['end_us'],
                        'activity':{k:{'mean':sum(v)/len(v),'peak':max(v),'end':v[-1]} for k,v in curves.items()},
                        'projected':{f'{regime}:{modality}':projection.project(process)
                                     for (regime,modality),(_,projection,_) in heads.items()}})
                for (regime,modality),(model,projection,calibration) in heads.items():
                    key=f'{regime}:{modality}'
                    for offset in range(0,len(rows),32):
                        batch=rows[offset:offset+32]
                        outputs=model.decode(calibration.transform([r['projected'][key]['values'] for r in batch]))
                        for r,text in zip(batch,outputs,strict=True):r.setdefault('text',{})[key]=text
                        guard(s)
                with gzip.open(target,'xt',encoding='utf-8') as stream:
                    for r in rows:
                        r['magnitude']={k:v['raw_sum'] for k,v in r.pop('projected').items()}
                        stream.write(encoded(r).decode()+'\n')
                summary.append({'source':source,'seed':seed,'condition':condition,'windows':len(rows),
                    'start_seconds':266,'end_seconds':boundary,'unique_frames':unique_frames,
                    'candidate':candidate,'texts':{f'{r}:{m}':dict(Counter(row['text'][f'{r}:{m}']['text'] for row in rows)) for r,m in heads},
                    'active_windows':{k:sum(row['activity'][k]['peak']>1e-8 for row in rows) for k in domains},
                    'last_activity':rows[-1]['activity']})
                if candidate and not any(c['seed']==seed for c in candidates):candidates.append(candidate)
                print(json.dumps({'continuous':source,'windows':len(rows),'candidate':candidate}),flush=True)
            del heads
        elapsed=time.monotonic()-started
        new_json(HERE/'continuous-results.json',{'sources':summary,'candidates':candidates,
            'window_seconds':2,'hop_seconds':.5,'background':'recorded physical telemetry',
            'overlap':'normal first60s also occur in background branch; these are not independent replications',
            'interpretation':'passive unedited text; no voluntary speech or logic inferred'})
        new_json(WORK/'timing'/'continuous.json',{'wall_seconds':elapsed})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':run()
