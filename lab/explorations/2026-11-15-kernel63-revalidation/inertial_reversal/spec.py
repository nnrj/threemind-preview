"""Finite registered contrasts and authentic E18 input schedules; no Core advancement."""
import gzip
import json
from pathlib import Path

SEEDS=(930101,930102,930103,930104)
PRESETS=('ordinary','facilitation')
MODES=('full','no_imu','dose_matched','shuffled_imu','untrained')
VARIANTS=[
 ('v2','2',{},'stream'),('v63','6.3',{},'stream'),
 ('v2-prequeue','2',{},'prequeue'),('v63-prequeue','6.3',{},'prequeue'),
 ('v31','3.1',{},'stream'),('v51','5.1',{},'stream'),('v53','5.3',{},'stream'),
 ('v2-no-delete','2',{'prune_weight':0.},'stream'),
 ('v63-exponential','6.3',{'decay_curve':'exponential'},'stream'),
 ('v63-higher-prune','6.3',{'prune_weight':'calibrated'},'stream'),
 ('v63-exp-prune','6.3',{'decay_curve':'exponential','prune_weight':'calibrated'},'stream'),
 ('v63-no-fatigue','6.3',{'strong_fatigue_enabled':False},'stream'),
 ('v31-no-fatigue','3.1',{'strong_fatigue_enabled':False},'stream'),
 ('v63-signal004','6.3',{'signal_threshold':.004},'stream'),
 ('v63-no-inhibitory-learning','6.3',{'inhibitory_learning_enabled':False},'stream'),
 ('v63-zero-sender-gates','6.3',{'activation_send_threshold':0.,'inhibition_send_threshold':0.},'stream'),
 ('v63-no-context','6.3',{'context_mix':0.},'stream')]

def load(p):
    b=Path(p).read_bytes()
    return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)

def frames(path):
    values=[json.loads(x) for x in gzip.decompress(Path(path).read_bytes()).splitlines()]
    rows=[v for v in values if 'stimulus' in v]
    assert rows and all(r['status']=='delivered' and r['scheduled_time_us']==r['delivered_time_us'] for r in rows)
    return [{'stimulus':r['stimulus'], 'enqueue_us':int(r['source_policy']['resolved_at_us']),
             'old_event_id':r['core_event_id'],'source':r['source']} for r in sorted(rows,key=lambda r:r['core_event_id'])]

def subjects(threshold):
    result=[]
    for name,version,patch,queue in VARIANTS:
        patch={k:threshold if v=='calibrated' else v for k,v in patch.items()}
        for seed in SEEDS:
            for preset in PRESETS:
                for mode in MODES if name in ('v2','v63') else ('full','no_imu'):
                    key=f'{name}-{seed}-{preset}-{mode}'
                    result.append({'key':key,'variant':name,'kernel':'threemind.continuous-memory/'+version,
                        'seed':seed,'preset':preset,'mode':mode,'queue_policy':queue,
                        'config':{'seed':seed,'stp_facilitation_tau_s':1. if preset=='facilitation' else 0.,**patch}})
    assert len(result)==320
    return result

def stages(subject):
    rows=[{'name':'teaching','begin_us':0,'end_us':19200000,'parent':None},
          {'name':'wait1','begin_us':19200000,'end_us':20200000,'parent':'teaching'}]
    for arm,patch in [('intact',{})]+([('test-no-inhibition',{'inhibition':False}),('test-no-fast',{'fast_enabled':False})]
              if subject['variant'] in ('v2','v63') and subject['mode'] in ('full','no_imu') else []):
        for sign in (0,1,-1):
            rows.append({'name':f'{arm}-{sign}','begin_us':20200000,'end_us':25800000,'parent':'wait1',
                         'sign':sign,'arm':arm,'test_patch':patch})
    return rows

def physical_folder(root,subject,stage):
    s=subject
    if stage['name']=='teaching':
        return root/'memory'/str(s['seed'])/s['preset']/s['mode']/'train'
    if stage['name']=='wait1':
        return root/'memory'/str(s['seed'])/s['preset']/s['mode']/'wait-1'
    return root/'transfer'/str(s['seed'])/s['preset']/s['mode']/'original'/str(stage['sign'])

def inputs(root,subject,stage,mappings):
    if stage.get('sign')==0:
        rows=[{'stimulus':{'time_us':str(t),'channels':[[mappings['keep'],1.]],'intensity':.2},
               'enqueue_us':stage['begin_us'],'old_event_id':i,'source':'maintenance-control'}
              for i,t in enumerate(range(20500000,25800000,500000))]
    else:
        rows=frames(physical_folder(root,subject,stage)/'inputs-frames.jsonl.gz')
    if subject['queue_policy']=='prequeue':
        rows=sorted(rows,key=lambda r:(r['source']=='maintenance-control',r['old_event_id']))
        rows=[dict(r,enqueue_us=stage['begin_us']) for r in rows]
    assert all(stage['begin_us']<=r['enqueue_us']<=int(r['stimulus']['time_us'])<=stage['end_us'] for r in rows)
    assert all(a['enqueue_us']<=b['enqueue_us'] for a,b in zip(rows,rows[1:]))
    if 'sign' in stage:
        assert not any(ch in (mappings['A'],mappings['B']) for r in rows for ch,value in r['stimulus']['channels'])
    return rows
