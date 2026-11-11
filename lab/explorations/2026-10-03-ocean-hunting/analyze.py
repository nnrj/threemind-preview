"""Process and outcome attribution for prospective full-habitat encounters."""
import gzip
import json
import numpy as np
from experiment import WORK,ARMS
from lab.tools.ocean_cli import read_json,write_json


def compressed(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def action_difference(left,right):
    left={r['t']:r for r in left};right={r['t']:r for r in right};out={}
    for end in (.5,2,6,20):
        times=[t for t in sorted(left.keys()&right.keys()) if t<end and left[t]['physical'] and right[t]['physical']]
        delta=np.asarray([np.asarray(left[t]['action'])-right[t]['action'] for t in times])
        out[str(end)]={'common_alive_s':len(times)*.02,
            'mae':float(np.abs(delta).mean()) if times else None,
            'first_observed_difference_s':next((t for t,d in zip(times,delta) if np.abs(d).max()>1e-8),None)}
    return out


def activity_difference(left,right,targets):
    left={r['t']:r for r in left};right={r['t']:r for r in right};a=b=0.;count=0
    for t in sorted(left.keys()&right.keys()):
        if not 1<=t<10:continue
        direct=set(left[t]['recent_channels'])|set(right[t]['recent_channels'])
        other={n['id']:n for n in right[t]['nodes']}
        for n in left[t]['nodes']:
            if n['id'] not in targets or n['channel'] in direct or n['id'] not in other:continue
            a+=n['activation']*.1;b+=other[n['id']]['activation']*.1;count+=1
    return {'samples':count,'intact_activation_seconds':a,'other_activation_seconds':b,'intact_minus_other':a-b}


def case_summary(folder,item):
    cache=WORK/'analysis-cases'/f'{folder.name}.json'
    if cache.exists():return read_json(cache)
    result=read_json(folder/'result.json');events=read_json(folder/'events.json');t0=item['time_us']
    focal,target=item['focal'],item['target']
    important=[e for e in events if e.get('individual') in (focal,target) or e.get('predator')==focal]
    capture=next((e for e in events if e['kind']=='body_engulfed' and e['individual']==target),None)
    focal_capture=next((e for e in events if e['kind']=='body_engulfed' and e['individual']==focal),None)
    out={k:result[k] for k in ('status','focal','target','operation','first_contact_s','windows','food','captured','physical','consumed_by','wall_seconds')}
    out.update(target_captured_by=capture['predator'] if capture else None,
        target_capture_s=(capture['time_us']-t0)/1e6 if capture else None,
        focal_capture_s=(focal_capture['time_us']-t0)/1e6 if focal_capture else None,
        target_captured_by_focal=capture is not None and capture['predator']==focal,
        events=important)
    write_json(cache,out);return out


def summarize():
    findings={'sources':{},'independent_world_seeds':2,'selection':[]}
    for source in sorted((WORK/'selections').glob('*/encounter.json')):
        item=read_json(source);key=source.parent.name;arms={};traces={};activity={}
        for op in ARMS:
            folder=WORK/'cases'/f'{key}-{op}'
            if not (folder/'result.json').exists():continue
            arms[op]=case_summary(folder,item)
        cache=WORK/'comparison-cache'/f'{key}.json'
        comparisons=read_json(cache) if cache.exists() else {}
        for left,right in (('intact','target'),('intact','matched'),('intact','random'),
            ('experienced','blank'),('experienced','graft'),('experienced','graft-matched')):
            name=left+' vs '+right
            if left in arms and right in arms and name not in comparisons:
                for op in (left,right):
                    if op not in traces:traces[op]=compressed(WORK/'cases'/f'{key}-{op}'/'trajectory.json.gz')
                comparisons[name]=action_difference(traces[left],traces[right])
        for op in ('target','matched'):
            name='uncued intact vs '+op
            if 'intact' in arms and op in arms and name not in comparisons:
                for a in ('intact',op):
                    if a not in activity:activity[a]=compressed(WORK/'cases'/f'{key}-{a}'/'activity.json.gz')
                comparisons[name]=activity_difference(activity['intact'],activity[op],set(item['plan']['targets']))
        cache.parent.mkdir(exist_ok=True);cache.write_text(json.dumps(comparisons),encoding='utf-8')
        findings['sources'][key]={'focal':item['focal'],'target':item['target'],'time_us':item['time_us'],
            'selected_edges':item['plan']['selected_edges'],'arms':arms,'comparisons':comparisons}
    for result in sorted((WORK/'cases').glob('scout-*/result.json')):findings['selection'].append(read_json(result))
    temporary=WORK/'findings.tmp';temporary.write_text(json.dumps(findings,ensure_ascii=False),encoding='utf-8')
    temporary.replace(WORK/'findings.json')
    print(json.dumps({'sources':{k:{'focal':v['focal'],'target':v['target'],'arms':{op:{p:c[p] for p in
        ('captured','target_captured_by_focal','target_capture_s','first_contact_s','physical')} for op,c in v['arms'].items()}}
        for k,v in findings['sources'].items()}}))
    return findings


if __name__=='__main__':summarize()
