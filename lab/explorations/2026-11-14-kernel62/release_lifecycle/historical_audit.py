"""Inspect delivered historical process records without running an individual."""
import argparse
import importlib.util
import json
import lzma
from pathlib import Path

spec=importlib.util.spec_from_file_location('r51t10_readonly_audit',Path(__file__).with_name('audit.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def run(work):
    a.s.check(work)
    result=[]
    for item in a.s.s.read(work/'historical.json'):
        folder=work/item['folder'];record=a.s.s.read(folder/'result.json')
        for name in ('initial','final'):
            state=a.s.s.ArtifactCodec.decode((folder/(name+'.tmind')).read_bytes())
            assert state.digest==record[name+'_sha256']
        points=json.loads(lzma.open(folder/'trajectory.json.xz','rb').read())['points']
        assert len(points)==1502
        times=[int(p['time_us'])-record['begin_us'] for p in points]
        assert times==[0]+list(range(0,15000001,10000))
        result.append(item|a.stats(points))
    for name,sha in a.s.s.read(work/'external-manifest.json').items():assert a.s.s.sha(Path(name))==sha
    a.s.s.write(work/'historical-only-audit.json',{'passed':True,'readonly':True,'records':result})
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);run(p.parse_args().work)
