"""Read-only reconstruction of the historical, channel-based E43 features."""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_spaced as m


def features(process,seed,bins=4,buckets=64):
    start=int(process['start_us']);end=int(process['planned_end_us'])
    groups=[[[] for _ in range(buckets)] for _ in range(bins)]
    counts=[0]*bins
    for point in process['trajectory']:
        index=min(bins-1,(int(point['time_us'])-start)*bins//max(1,end-start))
        assert 0<=index<bins
        counts[index]+=1
        for node in point['nodes']:
            if node['activation']<=0:continue
            key=f"language-readout/1:{seed}:{node['channel']}".encode()
            number=int.from_bytes(hashlib.blake2s(key,digest_size=4).digest(),'big')
            groups[index][number%buckets].append(node['activation']*(1 if number&0x80000000 else -1))
    return [math.fsum(values)/max(1,counts[i]) for i,group in enumerate(groups) for values in group],counts


def verify_historical(output):
    assert not output.exists()
    count=0;maximum=0.;relabelled=0;files=[]
    for path in sorted((m.OLD/'cases').glob('*/observations.jsonl.gz')):
        result=m.read(path.parent/'result.json');seed=result['seed']
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            rows=[json.loads(line) for line in stream]
        assert len(rows)==4
        for row in rows:
            process=row['process'];values,counts=features(process,seed)
            assert counts==process['samples_per_bin']
            assert row['features']==process['features']==result['windows'][row['window']]['features']
            error=max(abs(a-b) for a,b in zip(values,row['features'],strict=True))
            assert error<1e-12,(path,row['window'],error)
            maximum=max(maximum,error);count+=1
            if row['window']==1:
                altered=copy.deepcopy(process)
                for point in altered['trajectory']:
                    for index,node in enumerate(point['nodes']):node['id']=str(2**40-index)
                changed,_=features(altered,seed)
                assert changed==values
                relabelled+=1
        files.append({'path':path.relative_to(m.OLD).as_posix(),'sha256':m.sha(path),'windows':len(rows)})
    assert count==1960 and relabelled==490
    proof={'passed':True,'created_engines':0,'created_decoders':0,'windows':count,
           'node_identifier_relabelings':relabelled,'maximum_arithmetic_error':maximum,
           'feature_fields':['activation'],'identity_basis':'channel','features':256,
           'source_sha256':m.sha(Path(__file__)),'historical_files':files}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(proof,stream,ensure_ascii=False,sort_keys=True)
    print(json.dumps({k:v for k,v in proof.items() if k!='historical_files'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    verify_historical(p.parse_args().output.resolve())
