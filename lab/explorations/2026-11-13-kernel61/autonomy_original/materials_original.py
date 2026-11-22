"""Read-only E15 ancestry and material inventory; no Core is constructed."""
from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCES={
    'selection':(ROOT/'.work/input-rate-autonomy-20260929','59aee7a1-5248-417f-a03b-b56f858a04d9'),
    'internal':(ROOT/'.work/internal-activity-20260929','df63c577-3b39-4642-87c5-2e9e1b05f165'),
    'main':(ROOT/'.work/experience-autonomy-20260929','92548061-22c0-4bd9-b283-c4e1e7f4360d'),
}

def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory():
    values={};selected={}
    for source,(root,project) in SOURCES.items():
        for path in (root/'cases').rglob('result.json'):
            v=read(path)
            assert v['id'] not in values
            values[v['id']]={'source':source,'project':project,'value':v,'path':path}
    champions=[c for c in read(SOURCES['selection'][0]/'selection-results.json')['champions'] if c['arm']!='random']
    assert len(champions)==4 and {c['seed'] for c in champions}=={9293201,9293202}
    ancestry=[]
    for champ in champions:
        chain=[];identifier=champ['id']
        while identifier:
            v=values[identifier];assert v['source']=='selection'
            selected[identifier]=v;chain.append(identifier)
            identifier=v['value']['extra'].get('parent')
        assert len(chain)==3
        ancestry.append({'seed':champ['seed'],'arm':champ['arm'],'chain':list(reversed(chain))})
    for identifier,row in values.items():
        v=row['value'];key=v['key']
        if row['source']=='main' or (row['source']=='internal' and
                (key.startswith('warm/') or key.startswith('experience/') and key.endswith('/normal'))):
            selected[identifier]=row
    assert Counter(r['source'] for r in selected.values())=={'selection':12,'internal':12,'main':802}
    by_key={(r['source'],r['value']['key']):i for i,r in selected.items()}
    cases=[]
    for identifier,row in selected.items():
        v=row['value'];ex=v['extra'];source=row['source'];key=v['key']
        parent=ex.get('parent');born=bool(ex.get('born'))
        if source=='selection':born=parent is not None
        elif source=='internal':born=key.startswith('warm/')
        elif not parent:
            if ex['stage']=='memory-wait':parent=by_key['main',key.rsplit('/',1)[0]+'/train']
            elif ex['stage'] in ('memory-training','texture-primer'):parent=by_key['internal',f"warm/s{v['seed']}/region0"]
            else:raise AssertionError((key,ex['stage']))
        assert not parent or parent in selected,key
        begin=0 if born or not parent else int(selected[parent]['value']['time_us'])
        if 'begin_us' in ex:assert ex['begin_us']==begin,(key,ex['begin_us'],begin)
        assert v['life']=='active' and int(v['time_us'])>begin
        cases.append({'key':source+'/'+key,'source':source,'old_key':key,'old_id':identifier,
            'old_project':row['project'],'old_result_sha256':sha(row['path']),
            'old_state_sha256':v['state_sha256'],'old_kernel':v['kernel'],'seed':v['seed'],
            'parent_id':parent,'birth_intervention':born,'begin_us':begin,'end_us':int(v['time_us']),
            'historical_input_replay':source in ('selection','internal'),
            'new_closed_loop':source=='main' and ex.get('stage')=='environment',
            'family':ex.get('family',ex.get('stage',ex.get('kind'))),
            'old_config':v['config'],'old_readout_config':v['session']['configuration'],
            'old_wall_seconds':v['wall_seconds'],'historical_details':ex})
    order=[];left={c['old_id']:c for c in cases}
    while left:
        ready=sorted((c for c in left.values() if not c['parent_id'] or c['parent_id'] not in left),key=lambda c:c['key'])
        assert ready,'cyclic ancestry'
        for c in ready:order.append(left.pop(c['old_id']))
    assert len(order)==826
    keys={c['old_id']:c['key'] for c in order}
    for c in order:c['parent']=keys.get(c['parent_id'])
    return {'created_engines':0,'material_parent_count':4,'wiring_blocks':2,'ancestry':ancestry,'cases':order}


def normalize(raw,case):
    records=[json.loads(line) for line in raw.splitlines()]
    header=records.pop(0)
    assert header['schema']=='threemind.input-audit/1' and header['run_id']==case['old_id']
    frames=[]
    for row in records:
        assert row['run_id']==case['old_id'] and row['status']=='delivered' and not row['labels']
        assert row['delivered_time_us']==row['scheduled_time_us']==row['stimulus']['time_us']
        at=int(row['source_policy']['resolved_at_us'])
        assert case['begin_us']<=at<=int(row['scheduled_time_us'])<=case['end_us'],case['key']
        frames.append({'enqueue_us':at,'stimulus':row['stimulus'],'source':row['source'],
                       'old_event_id':row['core_event_id'],'old_envelope':row['envelope_id'],
                       'frame_index':row['frame_index']})
    frames.sort(key=lambda r:(r['enqueue_us'],r['old_event_id']))
    return frames


def export(folder):
    """Copy immutable historical inputs through the research API, without simulation."""
    sys.path.insert(0,str(HERE.parent/'body_recovery'))
    import study_recovery as support
    import httpx
    data=inventory();folder.mkdir(parents=True,exist_ok=True)
    assert not (folder/'manifest.json').exists(),'completed material export must not be repeated'
    support.s.base.load_env();records=[]
    with support.s.base.OperationsClient(url='http://127.0.0.1:8877',
            username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        for index,case in enumerate(data['cases']):
            assert support.s.base.resource_check(folder)['safe']
            destination=folder/case['key'];destination.mkdir(parents=True,exist_ok=True)
            rawpath=destination/'frames.jsonl';receipt=destination/'receipt.json'
            if rawpath.exists():
                assert receipt.exists(),'incomplete export: preserve and inspect'
                saved=read(receipt);assert saved['sha256']==sha(rawpath)
            else:
                saved=client.request('GET',f"/api/v2/projects/{case['old_project']}/runs/{case['old_id']}/inputs/export",
                    params={'records':'frames','format':'jsonl'},output=rawpath,maximum=16*2**20)
                with receipt.open('x',encoding='utf-8') as stream:json.dump(saved,stream,sort_keys=True)
            rows=normalize(rawpath.read_bytes(),case)
            records.append({'key':case['key'],'sha256':saved['sha256'],'bytes':saved['bytes'],
                'frames':len(rows),'sources':dict(Counter(r['source'] for r in rows))})
            if (index+1)%64==0:print(json.dumps({'exported':index+1,'total':len(data['cases'])}),flush=True)
    data.update(inputs=records,total_frames=sum(r['frames'] for r in records),
                total_bytes=sum(r['bytes'] for r in records))
    with (folder/'manifest.json').open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,sort_keys=True)
    print(json.dumps({k:data[k] for k in ('total_frames','total_bytes','created_engines')}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('check','export'),nargs='?',default='check')
    parser.add_argument('--folder',type=Path);args=parser.parse_args()
    if args.action=='export':export(args.folder.resolve())
    else:
        result=inventory()
        print(json.dumps({'created_engines':0,'cases':len(result['cases']),
            'sources':dict(Counter(c['source'] for c in result['cases'])),
            'closed_loop_stages':sum(c['new_closed_loop'] for c in result['cases'])}))
