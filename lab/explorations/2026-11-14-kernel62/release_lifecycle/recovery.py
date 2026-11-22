"""Authorized R51t10 research-copy continuation; preserve the failed directory."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from uuid import uuid5
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t10_recovery_recorder',HERE/'recording_v2.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
s=r.s
PARENT='93be6e86084b5470215770eae9184b19e9430e19c87e4dde1717d6a41f3f8629'
KEY='persistent/p0-f0/0/train'


def verify_pack(path,manifest):
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist())=={v['path'] for v in manifest['members']}
        for v in manifest['members']:
            raw=z.read(v['path'])
            assert len(raw)==v['bytes'] and s.hashlib.sha256(raw).hexdigest()==v['sha256']


def prepare(old,work):
    import psutil
    assert old.resolve()!=work.resolve() and not work.exists()
    s.check(old)
    host=s.s.read(old/'host.json')
    if psutil.pid_exists(host['pid']):assert psutil.Process(host['pid']).create_time()!=host['created']
    assert s.s.read(old/'current.json')=={'complete':1,'last':KEY,'total':92}
    assert (old/'STOP').exists() and (old/'in-flight.json').exists()
    assert s.s.read(old/'interruption-publication/receipt.json')['execution_status']=='interrupted'
    for name in ('recording-v2-final-verification.json','recording-budget-verification.json'):
        assert s.s.read(old/name)['passed']
    parent=s.get(old/'cases'/KEY/'final.rstate.gz')
    assert parent.digest==PARENT and int(parent.to_dict()['time_us'])==81200000
    assert s.engine(state=parent).capture_state().digest==PARENT
    assert s.s.base.resource_check(old)['safe'] and shutil.disk_usage(old).free>29*2**30
    manifest=s.s.read(old/'interruption-manifest.json')
    verify_pack(old/'interruption-evidence.zip',manifest)
    for v in manifest['members']:assert s.s.sha(old/v['path'])==v['sha256'],v['path']
    # The original process is absent. Keep its marker and exact archived bytes.
    with s.s.base.worker_lock(old):
        work.mkdir()
        for name in ('materials','references','historical','frozen-source'):
            shutil.copytree(old/name,work/name)
        for name in ('plan.json','reference-manifest.json','external-manifest.json','historical.json',
                     'apparatus.json','frozen.json','registration.json','recording-v2-final-verification.json',
                     'recording-budget-verification.json','historical-only-audit.json'):
            shutil.copyfile(old/name,work/name)
        shutil.copytree(old/'cases'/KEY,work/'cases'/KEY)
        (work/'.research-records').mkdir()
        shutil.copyfile(old/'.research-records/identity.json',work/'.research-records/identity.json')
        prior=work/'prior-attempt';prior.mkdir()
        for name in ('STOP','in-flight.json','current.json','host.json','resource-summary.json',
                     'interruption-manifest.json','interruption-evidence.zip'):
            shutil.copyfile(old/name,prior/name)
        shutil.copyfile(old/'interruption-publication/receipt.json',prior/'receipt.json')
        authorization={'date':'2026-11-15','user_quote':'我有过这个要求吗，你可帮我回忆一下，告诉我为何会有这个要求。然后你可以另建副本继续',
            'scope':'preserve failed wait; new research copy from complete 81.2-second teaching state; no reteaching or criterion change',
            'old_work':str(old),'parent_key':KEY,'parent_sha256':PARENT,'completed_stages_reused':1,
            'planned_total':92,'new_stages_remaining':91,'continuous_across_failed_wait':False}
        s.s.write(work/'recovery-authorization.json',authorization)
        sources={p.relative_to(s.ROOT).as_posix():s.s.sha(p) for p in
                 (Path(__file__),HERE/'recording_v2.py',HERE/'recovery.zh.md',HERE/'recovery.en.md')}
        for rel in sources:
            target=work/'recovery-source'/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(s.ROOT/rel,target)
        s.s.write(work/'recording-v2-frozen.json',{'sources':sources,'parent_sha256':PARENT,
                    'authorization_sha256':s.s.sha(work/'recovery-authorization.json')})
        s.s.write(work/'current.json',{'complete':1,'last':KEY,'total':92})
        s.s.write(work/'initial-resources.json',s.s.base.resource_check(work))
    s.check(work)
    assert s.get(work/'cases'/KEY/'final.rstate.gz').digest==PARENT
    with s.pre.client_context() as client:
        rec=s.s.base.ResearchRecorder(work,s.s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'recovery-r1-doc-'+lang)),'request_id':str(uuid5(s.NS,'recovery-r1-save-'+lang)),
                      'expected_revision':0,'kind':'note','title':'R51t10 authorized research-copy continuation '+lang,
                      'markdown':(HERE/f'recovery.{lang}.md').read_text('utf8')})
        rec.append('stage','r51t10:recovery:r1',authorization,request_id=uuid5(s.NS,'recovery-r1-stage'))
        rec.finalize(status='running',request_id=uuid5(s.NS,'recovery-r1-running'))
        rec.synchronize(strict=True);assert rec.status['pending']==0
        s.s.write(work/'recovery-registration.json',{'record':rec.experiment,'pending':0,'status':'running'})
    print(json.dumps({'prepared':str(work),'parent':PARENT,'remaining':91,'pending':0}),flush=True)


def run(work):
    f=s.s.read(work/'recording-v2-frozen.json')
    assert s.s.sha(work/'recovery-authorization.json')==f['authorization_sha256']
    assert s.s.read(work/'recovery-authorization.json')['parent_sha256']==PARENT
    r.run(work)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--old',type=Path)
    a=p.parse_args();prepare(a.old,a.work) if a.action=='prepare' else run(a.work)
