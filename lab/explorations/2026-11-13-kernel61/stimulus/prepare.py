"""Freeze inputs, verify the measurement tool, then register R51d through the API."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'src'),str(HERE.parent)]
import support as s
import materials
import run as r

NS=UUID('1534fb47-d06f-52ab-a2e8-9abfe30d4e3f')
PROJECT='d0a04159-ee0f-4200-ada9-13d5ce7197b7'


def instrument_check(work):
    receipt=ROOT/'.work/kernel61-instrument-receipt/instrument-check.json'
    if receipt.exists():
        previous=json.loads(receipt.read_bytes())
        if previous.get('runner_sha256')==s.sha(HERE/'run.py'):
            s.base.original(work/'instrument-check.json',previous)
            return
    folder=ROOT/'.work/kernel61-stimulus-instrument'
    folder.mkdir(exist_ok=False)
    case={'key':'calibration','parent':None,'stage':'probe','config':{'seed':93177},
          'inputs':[{'kind':'probe','stimulus':r.Stimulus(i*100000,((5111,1.),(8111,.7)),.2).to_dict()} for i in range(3)],
          'target_us':1000000,'family':'instrument','condition':'paired'}
    result=r.trial(folder,case)
    plain=r.new_engine(case['config'])
    for row in case['inputs']:plain.inject(r.Stimulus.from_dict(row['stimulus']))
    plain.advance_to(case['target_us'])
    assert plain.capture_state().digest==result['final_sha256']
    state=r.ArtifactCodec.decode((folder/'cases/calibration/final.tmind').read_bytes())
    restored=r.new_engine(state=state)
    before=restored.capture_state();restored.observation_nodes();restored.metrics()
    assert before.digest==restored.capture_state().digest
    plain.advance_to(2000000);restored.advance_to(2000000)
    assert plain.capture_state().digest==restored.capture_state().digest
    observer=json.loads((folder/'cases/calibration/observer.json').read_bytes())
    session=r.ReadoutSession(r.new_engine(state=state),record=lambda _:None,state=observer)
    session.advance_to(2000000)
    assert session.engine.capture_state().digest==plain.capture_state().digest
    result={'passed':True,'kind':'isolated-instrument-calibration','scientific_origins':0,
            'observation_preserved_core':True,'complete_restore_continuation':True,
            'calibration_originals':str(folder),'final_sha256':plain.capture_state().digest,
            'runner_sha256':s.sha(HERE/'run.py')}
    s.base.original(work/'instrument-check.json',result)


def prepare(work):
    assert not work.exists(),'Prepared or incomplete work already exists; inspect, never overwrite'
    engineering=work.parent/'kernel61-v1'
    assert json.loads((engineering/'publication/completion.json').read_bytes())['pending']==0
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free>25*2**30+1664*2**20
    work.mkdir();dest=work/'materials';dest.mkdir()
    old=ROOT/'.work/stimulus-spacetime-20260930'
    sources={}
    for name in ['host-recording.json']+[f'physical-{t}-{seed}.json' for seed in materials.SEEDS for t in ('inertial-cart','gravity-pendulum')]:
        data=(old/name).read_bytes();(dest/name).write_bytes(data)
        sources[name]={'source':str(old/name),'sha256':s.sha(dest/name),'bytes':len(data)}
    cases=materials.cases(dest)
    for seed in materials.SEEDS:
        for preset in materials.PRESETS:
            for template in ('inertial-cart','gravity-pendulum'):
                matches=[c for c in cases if c['seed']==seed and c['preset']==preset and c['template']==template and c['stage']=='teaching' and c['condition'] in ('complete','split','shuffled')]
                doses=[];times=[]
                for c in matches:
                    d=Counter()
                    for row in c['inputs']:
                        stim=r.Stimulus.from_dict(row['stimulus'])
                        for channel,value in stim.channels:d[channel]+=value*stim.intensity
                    doses.append(d);times.append({int(x['stimulus']['time_us']) for x in c['inputs']})
                assert len(matches)==3 and times[0]==times[1]==times[2]
                assert all(set(d)==set(doses[0]) and all(abs(v-doses[0][k])<1e-10 for k,v in d.items()) for d in doses)
    s.base.original(work/'materials.json',sources)
    s.base.original(work/'cases.json',cases)
    instrument_check(work)
    from _threemind_native import _threemind_native as native
    paths=list(HERE.glob('*.py'))+list(HERE.glob('protocol.*.md'))
    paths += [ROOT/'src/threemind_kernels'/n for n in ('local61.py','local61_config.py','local61_native.py','decay61.py','registry.py')]
    paths += [ROOT/'src/threemind_runtime'/n for n in ('readout_session.py','readout_host.py','readout_config.py','event_observation.py','bus.py','body.py','random_stimuli.py','stimulus_units.py','telemetry.py')]
    frozen={'kernel':r.KERNEL,'native_path':native.__file__,'native_sha256':s.sha(native.__file__),
            'sources':{p.relative_to(ROOT).as_posix():s.sha(p) for p in paths},
            'cases_sha256':s.sha(work/'cases.json'),'materials':sources}
    s.base.original(work/'frozen.json',frozen)
    for p in paths:
        out=work/'frozen-source'/p.relative_to(ROOT);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(p.read_bytes())
    s.base.load_env()
    import os,httpx
    from threemind_lab.operations_client import OperationsClient
    with OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
         password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
         transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,PROJECT,client=client)
        rec.register({'source_key':'r51d:stimulus:6.1:20261113:v1','title':'R51d：刺激体、连接形成与保持的6.1复验',
                      'classification':'formal','execution_status':'running','executor':'ai','kernels':[r.KERNEL],
                      'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
                      'required_roles':['protocol','report','note','original'],
                      'metadata':{'encoding_blocks':2,'configuration_pairs':4,'condition_records':264,'historical_reference':'E17','kernel_version':'6.1',
                                  'complete_continuity':True,'declared_causal_copies':True,'budget_peak_bytes':1664*2**20}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                      'kind':'protocol','expected_revision':0,'title':'R51d protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        receipt={'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',receipt)
        print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    prepare(p.parse_args().work.resolve())
