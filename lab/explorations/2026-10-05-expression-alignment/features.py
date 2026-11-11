"""Read existing evidence once per required case; compare registered instruments."""
from collections import defaultdict,deque
import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
from experiment import OLD,WORK,SEEDS,study,guard,read_json,new_json,write_gzip
from lab.tools.expression_observation import ExpressionObservation
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import PrototypeLanguage

MODES=('absolute','paired','preceding','paired-inhibition')
STATES=(('normal',266),('normal',326),('continued',532),('continued',592),('reversal',532),
        ('reversal',592),('background',532),('background',592))


def load_process(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def preceding(parent,seconds):
    queue=deque(maxlen=4)
    with gzip.open(parent/f'process-{seconds}.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:queue.append(line)
    queue=[json.loads(line)['process'] for line in queue]
    frames=[];last=-1
    for chunk in queue:
        for frame in chunk['trajectory']:
            when=int(frame['time_us'])
            if when>last:frames.append(frame);last=when
    if len(queue)!=4 or int(queue[-1]['end_us'])-int(queue[0]['start_us'])!=2000000:
        raise ValueError('full2s preceding history required')
    return {'start_us':queue[0]['start_us'],'end_us':queue[-1]['end_us'],
            'planned_end_us':queue[-1]['end_us'],'trajectory':frames}


def observation(modality,mode):
    return ExpressionObservation(read_json(WORK/'projection.json')[modality],
        'paired' if mode=='paired-inhibition' else mode,
        ('activation','inhibition') if mode=='paired-inhibition' else ('activation',))


def index_cases():
    result={}
    for base in (OLD,WORK):
        for path in (base/'cases').glob('*/result.json'):
            meta=read_json(path)
            if meta.get('kind')!='probe' or meta.get('intervention')!='none':continue
            key=(meta['seed'],meta['condition'],meta['seconds'],meta['modality'],meta['item'],meta['variant'],meta['intensity'],meta['split'])
            if key in result:raise ValueError(f'duplicate evidence key: {key}')
            result[key]=(path.parent,meta)
    return result


def collect(s):
    index=index_cases();rows=[]
    for seed in SEEDS:
        for condition,seconds in STATES:
            history=preceding(OLD/'cases'/f's{seed}-{condition}',seconds)
            for modality in ('vision','words'):
                guard(s)
                selected=[(path,meta) for key,(path,meta) in index.items() if key[:4]==(seed,condition,seconds,modality)]
                baseline=load_process(index[(seed,condition,seconds,modality,-1,0,.5,'test')][0]/'process.json.gz')
                instruments={mode:observation(modality,mode) for mode in MODES}
                for path,meta in selected:
                    process=load_process(path/'process.json.gz')
                    projected={mode:instrument.project(process,baseline if mode.startswith('paired') else history if mode=='preceding' else None)
                               for mode,instrument in instruments.items()}
                    rows.append(meta|{'evidence':path.relative_to(OLD.parents[1]).as_posix(),
                                      'features':projected})
            print({'features':seed,'condition':condition,'seconds':seconds,'rows':len(rows)},flush=True)
    write_gzip(WORK/'features.json.gz',rows)
    return rows


def references(rows,mode,calibrate):
    train=[{'values':r['features'][mode]['values'],'text':r['target'],'split':'train'} for r in rows if r['split']=='train']
    calibration=FeatureCalibration.fit(train) if calibrate else None
    if calibration:
        train=[r|{'values':calibration.transform(r['values']).tolist()} for r in train]
    return PrototypeLanguage(train),calibration


def analyze(s,rows):
    details=[];summary=[]
    for mode in MODES:
        for calibrate in (False,True):
            for seed in SEEDS:
                for modality in ('vision','words'):
                    guard(s)
                    subset=[r for r in rows if r['seed']==seed and r['modality']==modality]
                    frozen=references([r for r in subset if r['condition']=='normal' and r['seconds']==266],mode,calibrate)
                    for condition,seconds in STATES:
                        current=[r for r in subset if (r['condition'],r['seconds'])==(condition,seconds)]
                        for regime in ('frozen266','refitted'):
                            model,calibration=frozen if regime=='frozen266' else references(current,mode,calibrate)
                            tests=sorted([r for r in current if r['split']=='test'],key=lambda r:(r['item'],r['variant']))
                            values=[r['features'][mode]['values'] for r in tests]
                            outputs=model.decode(calibration.transform(values) if calibration else values)
                            no_cue=next(o['text'] for r,o in zip(tests,outputs,strict=True) if r['item']==-1)
                            correct=specific=total=0
                            for row,output in zip(tests,outputs,strict=True):
                                ok=output['text']==row['target'];distinct=ok and output['text']!=no_cue
                                if row['item']>=0:total+=1;correct+=ok;specific+=distinct
                                details.append({k:row[k] for k in ('seed','condition','seconds','modality','item','variant','target','evidence')}|
                                    {'mode':mode,'calibrate':calibrate,'regime':regime,'output':output,'correct':ok,
                                     'cue_specific':distinct,'contrast_magnitude':row['features'][mode]['contrast_magnitude']})
                            summary.append({'mode':mode,'calibrate':calibrate,'seed':seed,'modality':modality,'condition':condition,
                                            'seconds':seconds,'regime':regime,'correct':correct,'cue_specific':specific,'total':total,
                                            'no_cue_output':no_cue})
    write_gzip(WORK/'feature-decodes.json.gz',details)
    candidates=[]
    for mode in MODES:
        for calibrate in (False,True):
            selection=[r for r in summary if r['mode']==mode and r['calibrate']==calibrate and r['seed'] in (137,163) and r['regime']=='refitted']
            gates=[]
            for modality in ('vision','words'):
                for condition,seconds in STATES:
                    pairs=[r for r in selection if (r['modality'],r['condition'],r['seconds'])==(modality,condition,seconds)]
                    if len(pairs)==2 and all(r['cue_specific']/r['total']>=.75 for r in pairs):
                        gates.append({'modality':modality,'condition':condition,'seconds':seconds})
            candidates.append({'mode':mode,'calibrate':calibrate,'gates':gates,
                'selection_score':sum(r['cue_specific'] for r in selection)/sum(r['total'] for r in selection)})
    allowed=[r for r in candidates if r['gates']]
    allowed.sort(key=lambda r:(-r['selection_score'],r['mode'].startswith('paired'),r['mode']=='paired-inhibition',MODES.index(r['mode']),r['calibrate']))
    result={'rows':len(rows),'summaries':summary,'candidates':candidates,'selected':allowed[0] if allowed else None}
    new_json(WORK/'feature-summary.json',result)
    print(json.dumps({'selected':result['selected'],'candidates':candidates}),flush=True)


def main():
    s=study();started=time.monotonic();s.active_case=SimpleNamespace(born_wall=started)
    try:
        rows=load_process(WORK/'features.json.gz') if (WORK/'features.json.gz').exists() else collect(s)
        analyze(s,rows)
        new_json(WORK/'timing/features.json',{'wall_seconds':time.monotonic()-started})
    finally:s.db.close()


if __name__=='__main__':main()
