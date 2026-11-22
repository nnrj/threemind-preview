"""Register and deliver bounded cost diagnosis through the existing research API."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import deliver as d

PROJECT='d0a04159-ee0f-4200-ada9-13d5ce7197b7'


def act(work,finish):
    if finish and (work/'publication/completion.json').exists():
        print((work/'publication/completion.json').read_text('utf-8'));return
    d.f.base.resource_check(work)
    work.mkdir(parents=True,exist_ok=True)
    with d.f.base.worker_lock(work),d.connection() as client:
        rec=d.f.base.ResearchRecorder(work,PROJECT,client=client)
        if (work/'.research-records/identity.json').exists():rec.resume_recording()
        else:
            rec.register({'source_key':'kernel60:cost-profile:20261113:v1','title':'R51b：6.0推进耗时定位',
                'classification':'development','execution_status':'running','executor':'ai',
                'kernels':['threemind.continuous-memory/5.1','threemind.continuous-memory/6.0'],
                'protocol':(HERE/'protocol.md').read_text('utf-8'),'protocol_version':d.f.sha(HERE/'protocol.md'),
                'required_roles':['protocol','report','note','original'],
                'metadata':{'engineering_only':True,'scientific_origins':0,'campaign_status':'paused-performance',
                            'authorization':'User explicitly requested performance diagnosis; production kernels unchanged.'}},
                request_id=d.ident('cost-register'))
            rec.text({'identity':str(d.ident('cost-protocol-doc')),'request_id':str(d.ident('cost-protocol')),
                      'kind':'protocol','expected_revision':0,'title':'R51b protocol / 协议',
                      'markdown':(HERE/'protocol.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        if not finish:
            result={'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
            rec.save_original('registration.json',json.dumps(result,indent=2).encode());print(json.dumps(result));return
        assert not list(work.rglob('in-flight.json'))
        summary=json.loads((work/'summary.json').read_bytes());assert summary['instrument_exact_state_match']
        audit=json.loads((work/'profile-analysis.json').read_bytes())
        assert audit['passed'] and audit['complete_state_files']==104 and audit['instrument_exact_state_matches']==21
        for p in HERE.iterdir():
            if p.suffix in ('.py','.md'):rec.save_original('tools/'+p.name,p.read_bytes())
        source=d.f.ROOT/'.work/kernel60-cost'
        rec.save_original('instrumentation.json',(source/'instrumentation.json').read_bytes())
        manifest=json.loads((source/'instrumentation.json').read_bytes())
        for rel,h in manifest['source_files'].items():
            assert d.f.sha(d.f.ROOT/rel)==h
            rec.save_original('production-source/'+rel,(d.f.ROOT/rel).read_bytes())
        for rel,h in manifest['modified_files'].items():
            assert d.f.sha(source/'checkout'/rel)==h
            rec.save_original('instrument-source/'+rel,(source/'checkout'/rel).read_bytes())
        rec.save_original('instrument-module/_threemind_native.pyd',(source/'python/_threemind_native.pyd').read_bytes())
        for lang in ('zh','en'):
            rec.text({'identity':str(d.ident('cost-report-doc-'+lang)),'request_id':str(d.ident('cost-report-'+lang)),
                      'kind':'report','expected_revision':0,'title':'R51b report '+lang,
                      'markdown':(HERE/f'report.{lang}.md').read_text('utf-8')})
        rec.text({'identity':str(d.ident('cost-note-doc')),'request_id':str(d.ident('cost-note')),
                  'kind':'note','expected_revision':0,'title':'R51b engineering scope',
                  'markdown':'Instrumented complete states equal production states. Parameter controls are isolated engineering diagnostics. '
                             'Production kernels and formal subjects were not changed. The scientific campaign remains paused.'})
        excluded={'.research-records','publication','readback'}
        files=sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&excluded
                     and p.name not in ('originals.zip','manifest.json') and not p.name.endswith('.lock'))
        assert not any(p.name.endswith('.partial') for p in files)
        members={'members':[{'path':p.relative_to(work).as_posix(),'bytes':p.stat().st_size,'sha256':d.f.sha(p)} for p in files]}
        total=sum(r['bytes'] for r in members['members'])
        assert total < 512*2**20, 'Engineering-original budget exceeded'
        assert shutil.disk_usage(work).free > 25*2**30 + 2*total + 64*2**20, 'Archive/readback peak does not fit'
        rec.save_original('manifest.json',json.dumps(members,sort_keys=True).encode())
        pack=work/'originals.zip'
        if not pack.exists():
            part=work/'originals.zip.partial'
            with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                for p in files+[work/'manifest.json']:archive.write(p,p.relative_to(work).as_posix())
            d.verify(part,members)
            part.rename(pack)
        d.verify(pack,members)
        for name,role,fmt in (('originals.zip','original','application/zip'),('manifest.json','manifest','application/json'),('summary.json','analysis','application/json')):
            p=work/name
            rec.attach({'logical_id':'r51b:'+name,'role':role,'label':'R51b '+name,'format':fmt,
                        'byte_count':p.stat().st_size,'sha256':d.f.sha(p),
                        'locator':{'kind':'file','resource_id':d.RESOURCE,'member':'cost-profile-v1/'+name}},request_id=d.ident('cost-attach-'+name))
        rec.synchronize(strict=True)
        args={'path':{'project':PROJECT,'experiment':rec.experiment},'query':{'hashes':True}}
        checked=client.call('records.verify',args)
        assert checked['coverage']=='verified' and not checked['problems']
        row=next(x for x in checked['evidence'] if x['logical_id']=='r51b:originals.zip')
        d.f.base.resource_check(work)
        dest=work/'readback/originals.zip';dest.parent.mkdir(exist_ok=True)
        if not dest.exists():client.call('records.download',{'path':{'project':PROJECT,'evidence':row['id']}},output=dest,maximum=pack.stat().st_size)
        assert d.f.sha(dest)==d.f.sha(pack);d.verify(dest,members)
        for lang in ('zh','en'):
            doc=client.request('GET',f'/api/v2/projects/{PROJECT}/research-documents/{d.ident("cost-report-doc-"+lang)}')
            assert doc['spec']['blocks'][0]['markdown']==(HERE/f'report.{lang}.md').read_text('utf-8')
        rec.finalize(request_id=d.ident('cost-finalize'));rec.synchronize(strict=True)
        checked=client.call('records.verify',args)
        assert checked['coverage']=='verified' and not checked['problems'] and rec.status['pending']==0
        result={'project':PROJECT,'record':rec.experiment,'coverage':'verified','pending':0,'campaign_status':'paused-performance',
                'members':len(members['members']),'archive_bytes':pack.stat().st_size,'archive_sha256':d.f.sha(pack)}
        rec.save_original('publication/completion.json',json.dumps(result,indent=2).encode());print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','finish']);p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();act(args.work.resolve(),args.action=='finish')
