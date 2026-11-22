"""Original E22A input inventory; read-only and without kernel construction."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'.work/recovery-reference-20261001/cases'
SEEDS=(930101,930102,930103,930104)
GROUPS=('W','S','N')


def parents():
    return [{'key':f'{seed}/{mode}/learn{learn}','seed':seed,'mode':mode,'learn':learn}
            for seed,mode,learn in itertools.product(SEEDS,('full','no_imu'),('01','11'))]


def stages(parent):
    rows=[]
    for bits in itertools.product((0,1),repeat=3):
        groups=[g for g,on in zip(GROUPS,bits) if on];label=''.join(groups) or 'none'
        for sign,physical in itertools.product((1,-1),(0,1)):
            rows.append({'key':f"cut/{parent['key']}/{label}/sign{sign}/physical{physical}",
                         'family':'cut','kind':'probe','groups':groups,'sign':sign,'physical':bool(physical),
                         'begin_us':20200000,'end_us':25800000,'delay_s':1})
    for delay in (10,30,60):
        prefix=f"recovery/{parent['key']}/wait{delay}";end=19200000+delay*1000000
        rows.append({'key':prefix+'/hold','family':'recovery','kind':'hold',
                     'begin_us':20200000,'end_us':end,'delay_s':delay})
        for sign,physical in itertools.product((1,-1),(0,1)):
            rows.append({'key':prefix+f'/sign{sign}/physical{physical}','family':'recovery','kind':'probe',
                         'begin_us':end,'end_us':end+5600000,'delay_s':delay,
                         'sign':sign,'physical':bool(physical)})
    return rows


def frames(stage):
    path=OLD/stage['key']/'inputs-frames.jsonl.gz'
    records=[json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    records=[r for r in records if 'stimulus' in r]
    assert records and all(r['status']=='delivered' and not r['labels'] for r in records)
    records.sort(key=lambda r:r['core_event_id'])
    rows=[{'enqueue_us':int(r['source_policy']['resolved_at_us']),'source':r['source'],
           'stimulus':r['stimulus'],'old_event_id':r['core_event_id']} for r in records]
    assert all(stage['begin_us']<=r['enqueue_us']<=int(r['stimulus']['time_us'])<=stage['end_us'] for r in rows)
    assert all(a['enqueue_us']<=b['enqueue_us'] for a,b in itertools.pairwise(rows))
    assert all(int(r['stimulus']['time_us'])==int(r['delivered_time_us']) for r in records)
    return rows


def check():
    count=inputs=size=0;hashes={};patterns={}
    for parent in parents():
        for stage in stages(parent):
            folder=OLD/stage['key'];result=json.loads((folder/'result.json').read_bytes());rows=frames(stage)
            assert result['kernel']=='threemind.continuous-memory/2'
            assert int(result['time_us'])==stage['end_us']
            if stage['kind']=='probe':
                targets=result['extra']['targets']
                assert not any(ch in targets for r in rows for ch,amplitude in r['stimulus']['channels'])
            if stage['family']=='cut':
                key=(parent['key'],stage['sign'],stage['physical'])
                normalized=[{k:r[k] for k in ('enqueue_us','source','stimulus')} for r in rows]
                if key in patterns:assert patterns[key]==normalized
                else:patterns[key]=normalized
            for name in ('result.json','inputs-frames.jsonl.gz'):
                p=folder/name;hashes[p.relative_to(OLD).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
            count+=1;inputs+=len(rows);size+=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    assert len(parents())==16 and count==752 and inputs==17888
    return {'passed':True,'created_engines':0,'material_blocks':4,'parent_references':16,
            'cut_diagnostics':512,'holding_stages':48,'later_diagnostics':192,'inputs':inputs,
            'stages':count,'historical_logical_bytes':size,'hashes':hashes}


if __name__=='__main__':
    print(json.dumps({k:v for k,v in check().items() if k!='hashes'}))
