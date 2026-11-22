"""Read-only E12 material inventory and API input export; never loads a Core."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=ROOT/'.work/memory-timescales-20260929'
PROJECT='cbde2d48-284d-4294-9184-89f439923547'
KERNEL='threemind.continuous-memory/6.3'
SEED=9291000
TOKENS={'A':2932,'B':4786,'C':6969,'D':2064,'E':1925}
FIELDS=('depletion_enabled','stp_facilitation_tau_s','edge_consolidation_enabled')


def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory():
    originals={}
    for path in sorted((OLD/'cases').rglob('result.json')):
        value=read(path)
        if not value['key'].startswith('validation/'):
            originals[value['key']]=value
    ids={v['id']:k for k,v in originals.items()}
    assert len(originals)==592 and len(ids)==592
    cases=[]
    for key,value in originals.items():
        ex=value['extra'];kind=ex['kind'];parent=None;patch={}
        if kind=='probe':parent=ids[ex['parent_id']]
        elif kind=='warm':parent=f"short/train-{int(ex['swap'])}"
        elif kind=='readout_wait':parent=key.replace('readout/','retention/').rsplit('/d',1)[0]+'/train'
        else:assert kind in ('sequence_training','pair_training')
        if kind=='warm' or key.startswith('history/'):
            patch={f:value['config'][f] for f in FIELDS}
        elif key.startswith('readout/') and kind=='probe':patch={'edge_consolidation_enabled':False}
        elif key.startswith('sustain/'):
            patch={'unchanged':{},'depletion-on':{'depletion_enabled':True},
                   'facilitation-off':{'stp_facilitation_tau_s':0.},
                   'both':{'depletion_enabled':True,'stp_facilitation_tau_s':0.},
                   'consolidation-off':{'edge_consolidation_enabled':False}}[key.rsplit('/',1)[1]]
        initial=int(originals[parent]['time_us']) if parent else 0
        end=int(value['time_us'])
        assert end>initial and value['life']=='active' and value['seed']==SEED
        if parent:
            actual={f:originals[parent]['config'][f] for f in FIELDS}|patch
            assert actual=={f:value['config'][f] for f in FIELDS},key
        cfg={f:value['config'][f] for f in FIELDS}
        item={'key':key,'old_id':value['id'],'kind':kind,'parent':parent,'begin_us':initial,'end_us':end,
              'initial_config':cfg,'patch':patch,'swap':ex.get('swap',ex.get('training',{}).get('swap')),
              'background':ex.get('background',True),'old_result_sha256':sha(OLD/'cases'/key/'result.json'),
              'old_state_sha256':value['state_sha256'],'old_wall_seconds':value['wall_seconds'],
              'old_readers':value['session']['configuration']}
        if kind=='probe':
            item.update(cue=ex['probe'],probe_start_us=int(ex['start_us']),delay_s=ex['delay_s'],
                        gap_s=ex['gap_s'],scope=ex.get('trajectory_scope','all'),old_samples=ex['samples'],
                        old_classification=ex['classification'],old_post_cue=ex['post_cue'])
            assert end-item['probe_start_us']==15000000
            with gzip.open(OLD/'cases'/key/'snapshots.json.gz','rb') as stream:
                item['milestones']=sorted(int(k) for k in json.load(stream) if k.isdecimal())
        cases.append(item)
    order=[];left={c['key']:c for c in cases}
    while left:
        ready=sorted(k for k,c in left.items() if not c['parent'] or c['parent'] not in left)
        assert ready,'cyclic lineage'
        for k in ready:order.append(left.pop(k))
    assert Counter(c['kind'] for c in order)=={'sequence_training':2,'pair_training':32,'warm':16,'readout_wait':32,'probe':510}
    assert {c['swap'] for c in order if c['parent'] is None}=={False,True}
    return order


def normalize(raw,case):
    rows=[json.loads(line) for line in raw.splitlines()]
    header=rows.pop(0)
    assert header['schema']=='threemind.input-audit/1' and header['run_id']==case['old_id']
    frames=[]
    for r in rows:
        assert r['run_id']==case['old_id'] and r['status']=='delivered' and not r['labels']
        assert r['delivered_time_us']==r['scheduled_time_us']==r['stimulus']['time_us']
        enqueued=int(r['source_policy']['resolved_at_us'])
        assert case['begin_us']<=enqueued<=int(r['scheduled_time_us'])<=case['end_us']
        frames.append({'enqueue_us':enqueued,'stimulus':r['stimulus'],'source':r['source'],
                       'old_event_id':r['core_event_id'],'old_envelope':r['envelope_id'],
                       'frame_index':r['frame_index']})
    frames.sort(key=lambda r:(r['enqueue_us'],r['old_event_id']))
    stimuli=[r for r in frames if r['source']!='host-telemetry']
    if case['kind']=='probe':
        names={'AB':['A','B'],'DB':['D','B'],'B':['B'],'A':['A'],'D':['D'],'none':[]}[case['cue']]
        assert len(stimuli)==len(names)
        for r,name in zip(stimuli,names):
            assert r['source']=='manual-probe' and r['stimulus']['channels']==[[TOKENS[name],1.0]]
            assert r['stimulus']['intensity']==.5
    elif case['kind'] in ('warm','readout_wait'):assert not stimuli
    else:
        old=read(OLD/'cases'/case['key']/'result.json')
        assert len(stimuli)==len(old['pulses'])
        for r,pulse in zip(stimuli,old['pulses']):
            assert r['stimulus']=={'time_us':pulse['start_us'],'channels':[[c,1.] for c in pulse['channels']],'intensity':pulse['dose']}
    return frames


def export(folder):
    sys.path.insert(0,str(HERE.parent/'body_recovery'))
    import study_recovery as support
    import httpx
    cases=inventory();folder.mkdir(parents=True,exist_ok=True)
    support.s.base.load_env();records=[]
    with support.s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        for i,c in enumerate(cases):
            support.s.base.resource_check(folder)
            dest=folder/c['key'];dest.mkdir(parents=True,exist_ok=True)
            rawpath=dest/'frames.jsonl';receipt=dest/'receipt.json'
            if rawpath.exists():
                assert receipt.exists(),'completed export without receipt: preserve and inspect'
                saved=read(receipt);assert saved['sha256']==sha(rawpath)
            else:
                saved=client.request('GET',f"/api/v2/projects/{PROJECT}/runs/{c['old_id']}/inputs/export",
                    params={'records':'frames','format':'jsonl'},output=rawpath,maximum=16*2**20)
                with receipt.open('x',encoding='utf-8') as f:json.dump(saved,f,ensure_ascii=False,sort_keys=True)
            normalized=normalize(rawpath.read_bytes(),c)
            records.append({'key':c['key'],'sha256':saved['sha256'],'bytes':saved['bytes'],'frames':len(normalized)})
            if (i+1)%32==0:print(json.dumps({'exported':i+1,'total':len(cases)}),flush=True)
    manifest={'cases':cases,'inputs':records,'total_frames':sum(r['frames'] for r in records),
              'total_bytes':sum(r['bytes'] for r in records),'original_project':PROJECT,'created_engines':0}
    with (folder/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,sort_keys=True)
    print(json.dumps({k:manifest[k] for k in ('total_frames','total_bytes','created_engines')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('check','export'));p.add_argument('--folder',type=Path)
    a=p.parse_args()
    if a.action=='check':print(json.dumps({'cases':len(inventory()),'created_engines':0}))
    else:export(a.folder.resolve())
