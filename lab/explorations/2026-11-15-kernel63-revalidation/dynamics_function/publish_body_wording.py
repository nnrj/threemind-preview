"""Append a dated correction through the API; never write historical data directories."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID,uuid5
import httpx

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as h
s=h.s
NS=UUID('e6a3b508-c32c-508e-95f4-0277be5362ab')
OLD=Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/closed-body61-v1')
REPORT=h.ROOT/'lab/explorations/2026-11-13-kernel61/dynamics_function/body_report'


def publish(work):
    if (work/'completion.json').exists():print((work/'completion.json').read_text('utf-8'));return
    completed=h.read(OLD/'publication/completion.json')
    assert completed['coverage']=='verified' and completed['pending']==0
    preserved={p.name:s.sha(p) for p in (OLD/'manifest.json',OLD/'publication/completion.json')}
    old_reports={p.name:s.sha(p) for p in REPORT.glob('report*.md')}
    executor='lab/explorations/2026-11-13-kernel61/dynamics_function/body.py'
    assert h.read(OLD/'frozen.json')['sources'][executor]==s.sha(h.ROOT/executor)
    source=OLD/'cases/0031-body/inputs.json.xz'
    frames=[v['stimulus'] for v in h.e.unpacked(source) if v['source']=='closed-loop-body']
    from threemind_runtime.adapters import channel_id
    mask=channel_id(930101,'world-port-v1:physical-world-v1',0)
    imu={((port<<20)|i)^mask for port in (0,1) for i in range(6)}
    assert len(frames)==400 and all(any(ch in imu for ch,value in v['channels']) for v in frames)
    work.mkdir(parents=True,exist_ok=True);s.base.load_env()
    with s.base.worker_lock(work),s.base.OperationsClient(url='http://127.0.0.1:8877',
        username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        recorder=s.base.ResearchRecorder(work,completed['project'],client=client)
        identity=work/'.research-records/identity.json'
        if not identity.exists():shutil.copyfile(OLD/'.research-records/identity.json',identity)
        recorder.resume_recording();assert recorder.experiment==completed['record']
        for lang in ('zh','en'):
            body=(REPORT/f'errata-20261116.{lang}.md').read_text('utf-8')
            recorder.save_original(f'errata-20261116.{lang}.md',body.encode('utf-8'))
            recorder.text({'identity':str(uuid5(NS,'document-'+lang)),'request_id':str(uuid5(NS,'text-'+lang)),
                'expected_revision':0,'kind':'report','title':'R51t3 online dose-matching correction 2026-11-16 '+lang,
                'markdown':body})
        evidence={'executed_method':'full sensory vector multiplied by joint-only total / full total',
            'source_sha256':s.sha(source),'executor_sha256':s.sha(h.ROOT/executor),
            'sampled_frames_with_inertial_channels':400,'original_reports_sha256':old_reports,
            'scientific_results_unchanged':True,'historical_directory_written':False}
        recorder.append('correction','r51t3:online-dose-matching-description:20261116',evidence,
            request_id=uuid5(NS,'correction'))
        recorder.synchronize(strict=True)
        for lang in ('zh','en'):
            doc=client.request('GET',f'/api/v2/projects/{completed["project"]}/research-documents/{uuid5(NS,"document-"+lang)}')
            assert doc['spec']['blocks'][0]['markdown']==(REPORT/f'errata-20261116.{lang}.md').read_text('utf-8')
        check=client.call('records.verify',{'path':{'project':completed['project'],'experiment':recorder.experiment},
            'query':{'hashes':True}})
        assert check['coverage']=='verified' and not check['problems'] and recorder.status['pending']==0
        assert all(s.sha(REPORT/name)==digest for name,digest in old_reports.items())
        assert s.sha(OLD/'manifest.json')==preserved['manifest.json']
        assert s.sha(OLD/'publication/completion.json')==preserved['completion.json']
        result={'coverage':'verified','pending':0,'record':recorder.experiment,'project':completed['project'],
            'documents_read_back':2,**evidence}
        s.base.original(work/'completion.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();publish(a.work.resolve())
