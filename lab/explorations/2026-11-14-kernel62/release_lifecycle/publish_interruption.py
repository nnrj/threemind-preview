"""Publish preserved incomplete evidence as interrupted, never as completed."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from uuid import uuid5
import zipfile

spec=importlib.util.spec_from_file_location('r51t10_interruption_helpers',Path(__file__).with_name('study.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def verify(pack,manifest):
    with zipfile.ZipFile(pack) as z:
        assert set(z.namelist())=={v['path'] for v in manifest['members']}
        for v in manifest['members']:
            raw=z.read(v['path']);assert len(raw)==v['bytes'] and hashlib.sha256(raw).hexdigest()==v['sha256']


def run(work):
    assert (work/'in-flight.json').exists() and (work/'STOP').exists()
    assert s.s.read(work/'current.json')['complete']==1
    assert s.s.read(work/'historical-only-audit.json')['passed']
    assert s.s.read(work/'recording-v2-final-verification.json')['passed']
    assert s.s.read(work/'recording-budget-verification.json')['passed']
    s.check(work)
    import psutil
    h=s.s.read(work/'host.json')
    if psutil.pid_exists(h['pid']):assert psutil.Process(h['pid']).create_time()!=h['created']
    with s.s.base.worker_lock(work),s.pre.client_context() as client:
        rec=s.s.base.ResearchRecorder(work,s.s.PROJECT,client=client);rec.resume_recording()
        for p in Path(__file__).parent.iterdir():
            if p.suffix in ('.py','.md','.json'):rec.save_original('interruption-tools/'+p.name,p.read_bytes())
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'interim-report-'+lang)),
                'request_id':str(uuid5(s.NS,'interim-report-save-'+lang)),'expected_revision':0,'kind':'report',
                'title':'R51t10 engineering delivery and interrupted comparison '+lang,
                'markdown':Path(__file__).with_name('report.'+lang+'.md').read_text('utf8')})
        note='Only the 81.2-second teaching stage completed. The next wait exceeded a wall-clock assertion because of redundant full-state hashing. Its in-flight marker and incomplete files are retained. This is an interrupted measurement, not a scientific negative. Recovery requires the author’s confirmation. Historical 300-second process evidence passed read-only verification. No completed subject was rerun.'
        rec.text({'identity':str(uuid5(s.NS,'interruption-note')),'request_id':str(uuid5(s.NS,'interruption-note-save')),
                  'expected_revision':0,'kind':'note','title':'R51t10 interruption and recovery boundary','markdown':note})
        rec.append('stage','r51t10:interruption:20261115',{'completed_stages':1,'planned_stages':92,
            'interrupted_key':'persistent/p0-f0/0/original/wait','cause':'wall budget assertion in passive recorder',
            'recovery_executed':False},request_id=uuid5(s.NS,'interruption-stage'))
        excluded={'.research-records','interruption-publication','interruption-readback'}
        files=sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&excluded
                     and not p.name.endswith('.lock') and p.name not in ('interruption-evidence.zip','interruption-manifest.json'))
        manifest={'scientific_status':'interrupted','members':[{'path':p.relative_to(work).as_posix(),'bytes':p.stat().st_size,'sha256':s.s.sha(p)} for p in files]}
        total=sum(v['bytes'] for v in manifest['members']);assert total<2**30
        assert shutil.disk_usage(work).free>25*2**30+2*total+64*2**20
        rec.save_original('interruption-manifest.json',json.dumps(manifest,sort_keys=True).encode())
        pack=work/'interruption-evidence.zip'
        if not pack.exists():
            with zipfile.ZipFile(pack,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for p in files:z.write(p,p.relative_to(work).as_posix())
        verify(pack,manifest)
        for name,role in (('interruption-evidence.zip','original'),('interruption-manifest.json','manifest'),('historical-only-audit.json','analysis')):
            p=work/name
            rec.attach({'logical_id':'r51t10:interrupted:'+name,'role':role,'label':name,
                'format':'application/zip' if name.endswith('.zip') else 'application/json','byte_count':p.stat().st_size,
                'sha256':s.s.sha(p),'locator':{'kind':'file','resource_id':'kernel60-revalidation-20261113','member':work.name+'/'+name}},
                request_id=uuid5(s.NS,'attach-interrupted-'+name))
        rec.synchronize(strict=True)
        args={'path':{'project':s.s.PROJECT,'experiment':rec.experiment},'query':{'hashes':True}}
        status=client.call('records.verify',args);assert status['coverage']=='verified' and not status['problems']
        evidence=next(v for v in status['evidence'] if v['logical_id']=='r51t10:interrupted:interruption-evidence.zip')
        out=work/'interruption-readback/originals.zip';out.parent.mkdir(exist_ok=True)
        if not out.exists():client.call('records.download',{'path':{'project':s.s.PROJECT,'evidence':evidence['id']}},output=out,maximum=pack.stat().st_size)
        assert s.s.sha(out)==s.s.sha(pack);verify(out,manifest)
        rec.finalize(status='interrupted',request_id=uuid5(s.NS,'finalize-interrupted'))
        rec.synchronize(strict=True);assert rec.status['pending']==0
        status=client.call('records.verify',args);assert status['execution_status']=='interrupted' and status['coverage']=='verified'
        result={'record':rec.experiment,'execution_status':'interrupted','scientific_complete':False,'coverage':'verified',
                'pending':0,'members':len(files),'archive_sha256':s.s.sha(pack),'archive_bytes':pack.stat().st_size}
        s.s.write(work/'interruption-publication/receipt.json',result)
        print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);run(p.parse_args().work)
