"""Export and verify only this study's inputs and fixed external source states."""
import gzip
import hashlib
import json
from collections import Counter

from common import ROOT, WORK, Study, encoded, read_json
from experiment import PREVIOUS_WORK, parents
from threemind_lab.inputs import export_stream

def run(study):
    destination=WORK/'external-evidence'
    destination.mkdir(exist_ok=True)
    sources=[ROOT/'.work/candidates-20260929/host-0.jsonl', ROOT/'.work/candidates-20260929/host-0.complete.json']
    manifest=[]
    for path in sources:
        target=destination/path.name
        raw=path.read_bytes()
        if target.exists(): assert target.read_bytes()==raw
        else: target.write_bytes(raw)
        manifest.append({'source':str(path.relative_to(ROOT)), 'path':target.relative_to(WORK).as_posix(),
                         'sha256':hashlib.sha256(raw).hexdigest()})
    for parent in parents():
        folder=PREVIOUS_WORK/'cases'/parent['key']
        target=destination/'source-parents'/str(parent['id'])
        target.mkdir(parents=True,exist_ok=True)
        for name in ('parent-state.json.gz','result.json'):
            raw=(folder/name).read_bytes()
            if (target/name).exists(): assert (target/name).read_bytes()==raw
            else: (target/name).write_bytes(raw)
            manifest.append({'source':str((folder/name).relative_to(ROOT)), 'path':(target/name).relative_to(WORK).as_posix(),
                             'sha256':hashlib.sha256(raw).hexdigest()})
    counts=Counter()
    fingerprints={}
    for path in sorted((WORK/'cases').rglob('result.json')):
        item=read_json(path)
        frames=[]
        for records in ('envelopes','frames'):
            output=path.parent/f'input-{records}.jsonl.gz'
            if not output.exists():
                with gzip.open(output,'wt',encoding='utf-8') as f:
                    for line in export_stream(study.db,study.project,item['id'],records=records,format='jsonl'):
                        f.write(line)
            with gzip.open(output,'rt',encoding='utf-8') as f:
                next(f)
                for line in f:
                    row=json.loads(line)
                    counts[records]+=1
                    if records=='frames':
                        counts['frame_status:'+row['status']]+=1
                        assert row['status']=='delivered'
                        assert int(row['scheduled_time_us'])==int(row['delivered_time_us'])
                        frames.append((row['scheduled_time_us'],row['stimulus']))
        fingerprints[item['key']]=hashlib.sha256(encoded(sorted(frames,key=lambda r:(int(r[0]),encoded(r[1]))))).hexdigest()
    matched=0
    matched_probes=0
    for key,value in fingerprints.items():
        if key.startswith('expression/'):
            assert value==fingerprints[key.rsplit('/',1)[0]+'/normal'], key
            matched+=1
        if key.startswith(('probe/','birth-probe/')):
            parts=key.split('/')
            reference='/'.join(parts[:3]+['P','normal',parts[-2],'on'])
            assert value==fingerprints[reference], key
            matched_probes+=1
    result={'counts':dict(counts),'expression_identical_input_streams':matched,
            'probe_identical_input_streams':matched_probes,
            'frame_fingerprints':fingerprints,'external_sources':manifest,'all_delivered_at_scheduled_time':True}
    (WORK/'input-export-audit.json').write_bytes(encoded(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ('frame_fingerprints','external_sources')}),flush=True)

if __name__=='__main__':
    study=Study()
    try: run(study)
    finally: study.db.close()
