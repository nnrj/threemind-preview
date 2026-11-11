"""Re-read declared raw evidence; classify without sample transformations."""
import argparse,gzip,json,time
from collections import defaultdict
from types import SimpleNamespace
import numpy as np
from experiment import *
from lab.tools.raw_state_expression import RawStateProjection,ridge_fit,ridge_predict

FIELDSETS={'activation':('activation',),'activity':('activation','inhibition'),
           'history':('activation','inhibition','trace','support','stability')}

def load_process(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)

def instrument(modality,fields,scope='all',samples=17):
    p=read_json(WORK/'projection.json')[modality]
    channels=set(p['channels'])|set(p['excluded_channels'])
    excluded=set(p['excluded_channels']) if scope=='cross' else set()
    return RawStateProjection(tuple(sorted(channels-excluded)),tuple(fields),samples,tuple(sorted(excluded)))

def collect(base,*,old_data=False,full=False,modality=None):
    rows=[]
    for file in sorted((base/'cases').glob('*/result.json')):
        r=read_json(file)
        if r.get('kind')!='probe' or r.get('seed') not in SEEDS:continue
        if modality is not None and r['modality']!=modality:continue
        if r.get('intervention','none')!='none':continue
        if bool(r.get('full_state',False))!=full:continue
        if old_data and r['condition'] not in ('normal','continued','reversal','cycle1','cycle2','frozen'):continue
        process=load_process(file.parent/'process.json.gz')
        r=r|{'evidence':str(file.parent.relative_to(ROOT)),'interval_us':r.get('interval_us',0),
             'condition':r.get('condition','frozen' if r.get('frozen') else 'normal'),
             'raw':{scope:instrument(r['modality'],FIELDSETS['history'],scope).project(process)['values'] for scope in ('all','cross')}}
        rows.append(r)
    return rows

def values(row,fields,scope):
    value=np.asarray(row['raw'][scope],dtype=np.float64).reshape(17,-1,6)
    columns=[0]+[FIELDSETS['history'].index(f)+1 for f in fields]
    return value[:,:,columns].reshape(17,-1)

def scored(train,test,fields,scope):
    if not train or not test:raise ValueError('missing partition')
    model=ridge_fit([{'values':values(r,fields,scope),'target':r['target'],'split':r['split']} for r in train])
    output=ridge_predict(model,[values(r,fields,scope) for r in test])
    no_cue={ (r['seed'],r['condition'],r['interval_us'],r['seconds'],r['modality']):p for r,p in zip(test,output) if r['item']<0}
    details=[]
    for r,p in zip(test,output):
        key=(r['seed'],r['condition'],r['interval_us'],r['seconds'],r['modality'])
        if key not in no_cue:raise ValueError('no-cue control missing')
        details.append({k:r[k] for k in ('seed','condition','interval_us','seconds','modality','item','variant','target','evidence')}|
                       {'output':p,'correct':r['item']>=0 and p==r['target'] and p!=no_cue[key]})
    return details

def summarize(details,keys):
    groups=defaultdict(list)
    for r in details:
        if r['item']>=0:groups[tuple(r[k] for k in keys)].append(r)
    return [dict(zip(keys,key))|{'correct':sum(r['correct'] for r in rows),'count':len(rows)} for key,rows in sorted(groups.items())]

def analyze_old(rows):
    details=[]
    for seed in SEEDS:
        for modality in ('vision','words'):
            own=[r for r in rows if r['seed']==seed and r['modality']==modality]
            for fieldname,fields in FIELDSETS.items():
                for scope in ('all','cross'):
                    for regime in ('frozen266','two-assignments','current'):
                        subsets=sorted({(r['condition'],r['seconds']) for r in own}) if regime=='current' else [('all',0)]
                        for condition,seconds in subsets:
                            train=[r for r in own if r['split']=='train' and
                                ((r['condition']==condition and r['seconds']==seconds) if regime=='current' else
                                 (r['condition']=='normal' and r['seconds']==266) if regime=='frozen266' else
                                 (r['condition'] in ('continued','reversal') and r['seconds']==532))]
                            if not train:continue
                            test=[r for r in own if r['split']=='test' and (regime!='current' or (r['condition']==condition and r['seconds']==seconds))]
                            details.extend(r|{'fields':fieldname,'scope':scope,'regime':regime} for r in scored(train,test,fields,scope))
    return {'summary':summarize(details,('regime','scope','fields','condition','seconds','modality')),'rows':details}

def analyze_timing(rows):
    details=[]
    for seed in SEEDS:
        for interval in INTERVALS:
            for modality in ('vision','words'):
                own=[r for r in rows if r['seed']==seed and r['interval_us']==interval and r['modality']==modality and r['condition']=='normal']
                if not own:continue
                for fieldname,fields in FIELDSETS.items():
                    for scope in ('all','cross'):
                        for regime in ('frozen266','current'):
                            for seconds in (266,326):
                                train=[r for r in own if r['split']=='train' and r['seconds']==(266 if regime=='frozen266' else seconds)]
                                test=[r for r in own if r['split']=='test' and r['seconds']==seconds]
                                if not train or not test:continue
                                details.extend(r|{'fields':fieldname,'scope':scope,'regime':regime} for r in scored(train,test,fields,scope))
    return {'summary':summarize(details,('regime','scope','fields','interval_us','seconds','modality')),'rows':details}

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('old','timing'));args=p.parse_args()
    s=study();tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        rows=collect(OLD,old_data=True)
        if args.operation=='timing':
            rows=[r for r in rows if r['condition']=='normal']+collect(WORK)
        guard(s);result=analyze_old(rows) if args.operation=='old' else analyze_timing(rows)
        result.update(source_records=len(rows),normalization='none',subtraction=False,classifier='raw ridge diagnostic, not language proof')
        new_json(HERE/f'raw-{args.operation}.json',result)
        new_json(WORK/'timing'/f'raw-{args.operation}.json',{'wall_seconds':time.monotonic()-tick})
        print(json.dumps({'operation':args.operation,'records':len(rows),'summary':result['summary'][:12]},ensure_ascii=False),flush=True)
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':main()
