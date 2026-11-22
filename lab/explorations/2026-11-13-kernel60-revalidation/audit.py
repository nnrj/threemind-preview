"""Independent arithmetic and artifact checks; never instantiates a Core."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

from threemind_runtime import ArtifactCodec


def read(path):
    return json.loads(path.read_bytes())


def check(work):
    foundation=work/'foundation-v1'
    diagnosis=work/'diagnosis-v1'
    assert (foundation/'STOP').exists() and read(foundation/'summary.json')['state']=='paused-performance'
    assert not list(work.rglob('in-flight.json'))
    counts=0
    summary=[]
    for location, pattern in ((foundation,'n1024-active/**/result.json'),(diagnosis,'r*/**/result.json')):
        for path in location.glob(pattern):
            r=read(path)
            for kind,filename in (('initial','initial.tmind'),('final','final.tmind')):
                data=(path.parent/filename).read_bytes()
                assert hashlib.sha256(data).hexdigest()==r['files'][kind]['sha256']
                assert len(data)==r['files'][kind]['logical_bytes']
                state=ArtifactCodec.decode(data)
                assert state.digest==r[kind+'_state']
                s=state.to_dict()
                assert s['dynamics']==r['kernel']
                assert int(s['time_us'])==(0 if kind=='initial' else r['internal_seconds']*1000000)
                assert len(s['nodes'])==len(s['edges'])==1024
                assert sorted(n['id'] for n in s['nodes'])==list(range(1,1025))
                counts+=1
            summary.append(r)
    assert len(summary)==32 and counts==64
    confirm=[r for r in summary if '/confirm' in r['key']]
    med={}
    for version in ('5.1','6.0'):
        rows=[r for r in confirm if r['kernel'].endswith('/'+version)]
        assert len(rows)==5
        med[version]={key:statistics.median(r['advance'][key] for r in rows) for key in ('wall_s','cpu_s')}
    wall_ratio=med['6.0']['wall_s']/med['5.1']['wall_s']
    cpu_ratio=med['6.0']['cpu_s']/med['5.1']['cpu_s']
    assert wall_ratio>=2 and cpu_ratio>=2
    original=read(foundation/'summary.json')['comparisons'][0]['confirmation']['advance']
    assert wall_ratio==original['wall_s']['ratio'] and cpu_ratio==original['cpu_s']['ratio']
    diag=read(diagnosis/'result.json')
    assert len(diag['standalone'])==8 and all(r['passed'] for r in diag['standalone'])
    assert diag['versions']['5.3']['audit']==diag['versions']['6.0']['audit']
    return {'passed':True,'complete_engineering_trials':32,'complete_benchmark_states':64,
            'standalone_continuations':8,'confirmed_wall_ratio':wall_ratio,'confirmed_cpu_ratio':cpu_ratio,
            'median_advance_seconds':med,'campaign_state':'paused-performance',
            'reviewer':'assistant arithmetic audit; not external replication'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();result=check(a.work)
    with (a.work/'audit-v1.json').open('x',encoding='utf-8') as out:
        json.dump(result,out,indent=2)
    print(json.dumps(result))
