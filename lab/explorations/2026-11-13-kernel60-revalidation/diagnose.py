"""Finish bounded engineering diagnosis after the main campaign has paused."""
import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess

import foundation as f
from threemind_kernels.decay60 import CURVES
from threemind_runtime.inheritance import birth


def same(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            same(a[k], b[k])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b, strict=True):
            same(x, y)
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=3e-12, abs_tol=3e-14), (a,b)
    else:
        assert a == b, (a,b)


def run(work):
    if work.exists():
        raise RuntimeError('fresh diagnostic directory required')
    work.mkdir(parents=True)
    f.base.original(work/'protocol.json', {'source_sha256':f.sha(Path(__file__)),
                    'protocol_sha256':f.sha(f.HERE/'diagnostic-protocol.md'), 'engineering_only':True})
    f.blob(work/'diagnostic-protocol.md', (f.HERE/'diagnostic-protocol.md').read_bytes())
    f.blob(work/'diagnose.py', Path(__file__).read_bytes())
    with f.base.worker_lock(work), f.base.Guard(work):
        rows=[]
        for repeat in range(5):
            for version in ('5.3','6.0')[::1 if repeat%2==0 else -1]:
                row=f.trial(work, f'r{repeat}/{version}', 'threemind.continuous-memory/'+version,512,False,10)
                state=f.ArtifactCodec.decode((work/row['key']/'final.tmind').read_bytes()).to_dict()
                rows.append(row|{'audit':state['audit']})
        result={'versions':{},'standalone':[]}
        for version in ('5.3','6.0'):
            items=[r for r in rows if r['kernel'].endswith('/'+version)]
            result['versions'][version]={'wall_median':statistics.median(r['advance']['wall_s'] for r in items),
                'cpu_median':statistics.median(r['advance']['cpu_s'] for r in items), 'audit':items[0]['audit']}
        executable=f.ROOT/'.work/native60-birth/release/threemind-runtime.exe'
        for curve in CURVES:
            for age in ('preserve','reset'):
                f.boundary(work)
                folder=work/f'standalone/{curve}/{age}'
                folder.mkdir(parents=True)
                d=f.resolve_kernel(f.KERNELS[1])
                e=d.create(d.configuration({'decay_curve':curve}),backend='native')
                e.inject(f.Stimulus(0, ((17,.8),(301,.7))))
                e.advance_to(233337)
                source=e.capture_state()
                image=birth(source,decay_age=age)
                f.blob(folder/'newborn.tmind',f.ArtifactCodec.encode(image,'tmind'))
                stimulus=f.Stimulus(7777,((17,.4),(301,.6)))
                f.blob(folder/'input.jsonl',(json.dumps(stimulus.to_dict())+'\n').encode())
                output=folder/'continued.tmind'
                invocation=subprocess.run([str(executable),'--model',str(folder/'newborn.tmind'),
                    '--input',str(folder/'input.jsonl'),'--until-us','230007','--clock','unbounded',
                    '--export',str(output)],capture_output=True,text=True,encoding='utf-8',check=True,timeout=45)
                resumed=d.create(state=image,backend='native')
                resumed.inject(stimulus);resumed.advance_to(230007)
                final=f.ArtifactCodec.decode(output.read_bytes())
                same(resumed.capture_state().to_dict(),final.to_dict())
                assert source.digest==e.capture_state().digest
                result['standalone'].append({'curve':curve,'age':age,'passed':True,'parent':source.digest,
                    'newborn':image.digest,'final':final.digest,'exe_sha256':f.sha(executable),'stdout':invocation.stdout})
        f.base.original(work/'result.json',result)
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
