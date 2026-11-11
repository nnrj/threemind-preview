"""Export and verify this study alone; no old evidence is overwritten."""
import gzip
import hashlib
import json
from collections import Counter
from common import ROOT,WORK,Study,encoded,read_json
from experiment import SOURCE,PARENTS,name
from threemind_lab.inputs import export_stream

def run(study):
    destination=WORK/'external-evidence';destination.mkdir(exist_ok=True)
    sources=[ROOT/'.work/candidates-20260929/host-0.jsonl',ROOT/'.work/candidates-20260929/host-0.complete.json']
    for seed,arm in PARENTS:
        for key in ('warm/'+name(seed,arm),*[f'experience/{name(seed,arm)}/{h}/normal' for h in ('P','Q')]):
            sources.extend(SOURCE/'cases'/key/f for f in ('result.json','parent-state.json.gz'))
    manifest=[]
    for path in sources:
        relative=path.relative_to(ROOT/'.work')
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        raw=path.read_bytes()
        if target.exists():assert target.read_bytes()==raw
        else:target.write_bytes(raw)
        manifest.append({'source':str(relative),'sha256':hashlib.sha256(raw).hexdigest()})
    counts=Counter();fingerprints={}
    for path in sorted((WORK/'cases').rglob('result.json')):
        item=read_json(path);frames=[]
        for kind in ('envelopes','frames'):
            target=path.parent/f'input-{kind}.jsonl.gz'
            if not target.exists():
                with gzip.open(target,'wt',encoding='utf-8') as f:
                    for line in export_stream(study.db,study.project,item['id'],records=kind,format='jsonl'):f.write(line)
            with gzip.open(target,'rt',encoding='utf-8') as f:
                next(f)
                for line in f:
                    row=json.loads(line);counts[kind]+=1
                    if kind=='frames':
                        assert row['status']=='delivered'
                        assert int(row['scheduled_time_us'])==int(row['delivered_time_us'])
                        frames.append((row['scheduled_time_us'],row['stimulus']))
        fingerprints[item['key']]=hashlib.sha256(encoded(sorted(frames,key=lambda r:(int(r[0]),encoded(r[1]))))).hexdigest()
    matched=0
    for key,fp in fingerprints.items():
        p=key.split('/')
        reference=None
        if p[0]=='local':reference='/'.join([*p[:3],'P','normal',p[-1]])
        elif p[0]=='sequence':reference='/'.join([*p[:3],'P','normal',p[-1]])
        elif p[0]=='memory-probe':reference='/'.join([*p[:2],'none',*p[3:5],'normal',p[-1]])
        elif p[0]=='environment-probe':reference='/'.join([*p[:3],'PPP',*p[4:]])
        elif p[0]=='retention-extension':reference='/'.join([*p[:2],'none','normal',p[-1]])
        if reference:
            assert fp==fingerprints[reference],(key,reference)
            matched+=1
    out={'counts':dict(counts),'matched_probe_streams':matched,'external_sources':manifest,
         'frame_fingerprints':fingerprints,'all_delivered_at_scheduled_time':True}
    (WORK/'input-export-audit.json').write_bytes(encoded(out))
    print(json.dumps({'counts':dict(counts),'matched_probe_streams':matched}),flush=True)

if __name__=='__main__':
    s=Study()
    try:run(s)
    finally:s.db.close()
