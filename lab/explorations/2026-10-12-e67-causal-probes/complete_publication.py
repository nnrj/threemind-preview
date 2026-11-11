"""Reconcile the rejected duplicate-role requests; never rerun a probe.

The frozen first publisher mistakenly requeued four protocol originals with a
process role. Only exact role-only duplicates of confirmed remote receipts may
be restored to their original queued request. Keep the rejected request bytes.
"""
import hashlib
import json
from pathlib import Path
from probe import (load_env, ResearchStorage, HERE, RESOURCE, read, write, recording,
                   sha, verify_sources, attach)
from threemind_lab.record_schema import AttachRecord
from threemind_lab.research_records import digest
from threemind_lab.storage_files import atomic_json, file_lock


def main():
    load_env();storage=ResearchStorage();work=storage.workspace_path(HERE.name)
    source=storage.workspace_path('2026-10-11-shape-color-kernels')
    verify_sources(source,work,read(work/'plan.json'))
    assert read(work/'complete.json')['sources_unchanged']
    c,rec,rid=recording(source,work)
    try:
        with storage.writer(RESOURCE):
            fixed=[]
            with file_lock(rec.control/'journal.lock'):
                for p in sorted((rec.control/'pending').glob('*.json')):
                    receipt=rec.control/'receipts'/p.name
                    if not receipt.exists():continue
                    pending=read(p);committed=read(receipt)['request']
                    if pending==committed:continue
                    if pending['action']!='attach' or committed['action']!='attach':raise ValueError('unexpected duplicate action')
                    old=committed['body']['evidence'];new=pending['body']['evidence']
                    expected=json.loads(json.dumps(pending));expected['body']['evidence']['role']=old['role']
                    if old['role']!='protocol' or new['role']!='process' or expected!=committed:
                        raise ValueError('not an exact protocol/process-only duplicate')
                    remote=c.call('records.receipt',{'path':{'project':rec.project,'request_id':committed['body']['request_id']}})
                    body=AttachRecord.model_validate(committed['body']).model_dump(mode='json')
                    fingerprint=digest({'action':'attach','value':{'id':rec.experiment,**body}})
                    if remote['fingerprint']!=fingerprint:raise ValueError('remote committed receipt differs')
                    if sha(work/old['locator']['member'])!=old['sha256']:raise ValueError('original bytes changed')
                    write(rec.control/'rejected-duplicates'/p.name,p.read_bytes())
                    atomic_json(p,committed)
                    fixed.append(dict(request_id=body['request_id'],logical_id=old['logical_id'],
                        original_role='protocol',rejected_role='process',sha256=old['sha256']))
            correction=work/'publication-correction.json'
            if not correction.exists():write(correction,dict(reason='Frozen publisher requeued protocol references with a different role; canonical server rejected conflict before mutation.',
                repaired=fixed,method='verify prior local and remote receipts and byte hashes; restore exact original request; preserve rejected bytes',
                no_core_change=True,no_experiment_rerun=True))
            rec.synchronize(strict=True)
            tool_source=work/'source-reference'/('complete_publication-'+sha(__file__)[:12]+'.py')
            write(tool_source,Path(__file__).read_bytes())
            for p in (correction,tool_source):attach(rec,rid,work,p,'process')
            rec.append('correction','causal-probes-20261012:publication',read(correction),request_id=rid('publication-correction'))
            rec.synchronize(strict=True)
            checks={}
            for lang in ('zh','en'):
                receipt=c.call('records.receipt',{'path':{'project':rec.project,'request_id':rid('report:'+lang)}})
                checks['report_'+lang]=receipt['result']['text']['id']
            qa=Path('.work/e67-causal-api-qa');qa.mkdir(parents=True,exist_ok=True)
            for member in ('analysis/summary.json','arms/2/final-0-0/silence/result.json','arms/3.1/final-0-3/silence/result.json'):
                receipt=c.call('records.receipt',{'path':{'project':rec.project,'request_id':rid('file:'+member)}})
                evidence_id=receipt['result']['id'];dest=qa/(evidence_id+'.json')
                if not dest.exists():c.request('GET',f"/api/v2/projects/{rec.project}/record-evidence/{evidence_id}/content",output=dest)
                if sha(dest)!=sha(work/member):raise ValueError('authenticated evidence read mismatch')
                checks[member]=dict(id=evidence_id,sha256=sha(dest))
            detail=c.call('records.detail',{'path':{'project':rec.project,'experiment':rec.experiment}})
            checks.update(experiment=rec.experiment,experiment_status=detail['execution_status'],pending=rec.status['pending'])
            write(work/'publication-verified.json',checks)
            attach(rec,rid,work,work/'publication-verified.json','result');rec.synchronize(strict=True)
            print(json.dumps(checks,ensure_ascii=False))
    finally:c.close()


if __name__=='__main__':main()
