"""Prospectively registered matched mechanism study; serial resumable execution."""
import argparse
from contextlib import contextmanager
import gc
import json
import os
from pathlib import Path
import shutil
import time
from uuid import uuid5
import apparatus as a
from lab.tools.study_lock import worker_lock

@contextmanager
def client_context():
    import httpx
    from threemind_lab.config import load_env
    from threemind_lab.operations_client import OperationsClient
    load_env()
    with OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        yield client

def native_path():
    from _threemind_native import _threemind_native as native
    return Path(native.__file__)

def register():
    a.guard()
    assert a.read(a.WORK/'apparatus.json')['passed']
    assert not (a.WORK/'science').exists()
    materials = [a.material(seed,i) for seed in a.SEEDS for i in a.HISTORIES]
    configs = {}
    for m in materials:
        a.save(a.WORK/'materials'/f'{m["key"]}.json.gz', m)
        configs[m['key']] = {p: a.Trial('config:'+p+':'+m['key'],p,m).engine.config.to_dict() for p in a.PROFILES}
    a.save(a.WORK/'configurations.json', configs)
    sources = [p for p in a.HERE.iterdir() if p.suffix in ('.py','.md')]
    production = [p for name in ('threemind_core','threemind_kernels','threemind_runtime')
                  for p in (a.ROOT/'src'/name).rglob('*.py')]
    frozen = {'sources': {str(p.relative_to(a.ROOT)): a.sha(p) for p in sources},
              'production': {str(p.relative_to(a.ROOT)): a.sha(p) for p in production},
              'native': {'path': str(native_path()), 'sha256': a.sha(native_path())},
              'prefix_source_sha256': a.sha(a.PROFILE_FILE),
              'materials': {m['key']:a.digest(m) for m in materials}, 'planned_stages':312,
              'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    a.save(a.WORK/'frozen.json', frozen)
    for p in sources + production + [a.PROFILE_FILE]:
        dest = a.WORK/'frozen-source'/p.relative_to(a.ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists(): shutil.copyfile(p,dest)
        assert a.sha(dest) == a.sha(p)
    from threemind_lab.research_recorder import ResearchRecorder
    with client_context() as client:
        rec = ResearchRecorder(a.WORK,a.PROJECT,client=client)
        protocol = '\n\n'.join((a.HERE/f'{name}.zh.md').read_text('utf8') for name in ('protocol','protocol-v2'))
        rec.register({'source_key':'as63-03:ring-mechanisms:20261118:v2',
            'title':'AS63-03：旧环形外设下的经历、出生继承与行为表达',
            'classification':'formal','execution_status':'running','executor':'ai',
            'kernels':[a.kernel('legacy1'),a.kernel('default63')],
            'protocol':protocol,'protocol_version':a.digest(protocol),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'peripheral_blocks':2,'historical_materials':4,'profiles':3,'planned_stages':312,
                        'energy_simulation_enabled':False,'no_production_changes':True}},
            request_id=uuid5(a.NS,'register'))
        for lang in ('zh','en'):
            text = '\n\n'.join((a.HERE/f'{name}.{lang}.md').read_text('utf8') for name in ('protocol','protocol-v2'))
            rec.text({'identity':str(uuid5(a.NS,'protocol-document-'+lang)),
                'request_id':str(uuid5(a.NS,'protocol-'+lang)),'expected_revision':0,
                'kind':'protocol','title':'AS63-03 protocol '+lang,'markdown':text})
        rec.synchronize(strict=True)
        a.save(a.WORK/'registration.json',{'project':a.PROJECT,'record':rec.experiment,
            'pending':rec.status['pending'],'registered_before_formal':True})
    print(json.dumps(a.read(a.WORK/'registration.json')),flush=True)

def frozen_check():
    frozen = a.read(a.WORK/'frozen.json')
    for relative, h in (frozen['sources']|frozen['production']).items(): assert a.sha(a.ROOT/relative)==h, relative
    assert a.sha(native_path()) == frozen['native']['sha256']
    assert a.read(a.WORK/'registration.json')['pending']==0
    return frozen

def old_witness(folder,m):
    rows = a.read(folder/'trajectory.json.gz')['rows']
    assert len(rows)==len(m['rows'])==600
    maximum, motor = 0.,0.
    for new,old in zip(rows,m['rows']):
        assert new['relative_us']==old['relative_us']
        nn={n['channel']:n['activation'] for n in new['nodes']}
        oo={n['channel']:n['activation'] for n in old['nodes']}
        assert nn.keys()==oo.keys()
        maximum=max(maximum,max((abs(nn[ch]-oo[ch]) for ch in nn),default=0.))
        motor=max(motor,abs(new['controls']['id']-old['proposed_control']))
    result={'activation_max_abs_error':maximum,'motor_max_abs_error':motor,'samples':600,
            'passed':maximum<=1e-10 and motor<=1e-10}
    a.save(folder/'historical-witness.json',result)
    assert result['passed'], result
    return result

def run():
    frozen=frozen_check()
    lock=worker_lock(a.WORK)
    started=time.monotonic()
    try:
        existing=list((a.WORK/'science').rglob('result.json'))
        used=sum(a.read(p)['wall_seconds'] for p in existing)
        count=len(existing)
        def bounded():
            a.guard()
            assert used+time.monotonic()-started<7200,'scientific wall budget'
            assert sum(p.stat().st_size for p in a.WORK.rglob('*') if p.is_file())<2**30,'original budget'
        for seed in a.SEEDS:
            for index in a.HISTORIES:
                m=a.read(a.WORK/'materials'/f's{seed}-c{index}.json.gz')
                assert a.digest(m)==frozen['materials'][m['key']]
                for profile in a.PROFILES:
                    bounded(); frozen_check()
                    folder=a.WORK/'science'/m['key']/profile
                    def execute(suffix,**kwargs):
                        nonlocal count
                        target=folder/suffix
                        before=(target/'result.json').exists()
                        result,state=a.execute(target,m['key']+':'+profile+':'+suffix,profile,m,**kwargs)
                        if not before: count+=1
                        print(json.dumps({'stages':count,'planned':312,'material':m['key'],'profile':profile,
                            'latest':suffix,'region1':result['region1'],'wall_s':round(result['wall_seconds'],2)}),flush=True)
                        return result,state
                    _,developed=execute('teaching',mode='replay')
                    if profile=='legacy1': old_witness(folder/'teaching',m)
                    blank=a.Trial(m['key']+':'+profile+':blank',profile,m).snapshot()
                    child_obj=a.Trial(m['key']+':'+profile+':birth',profile,m,parent=developed)
                    newborn=child_obj.snapshot()
                    a.save(folder/'birth.json',{'metadata':child_obj.ancestry,
                        'parent_hash':a.digest(developed),'child_hash':a.digest(newborn)})
                    a.save(folder/'newborn.json.gz',newborn)
                    a.save(folder/'blank.json.gz',blank)
                    _,redeveloped=execute('offspring-teaching',whole=newborn,mode='replay',position=.125 if index==0 else .625)
                    states={'blank':blank,'parent':developed,'newborn':newborn,'redeveloped':redeveloped}
                    for label,state in states.items():
                        before=a.digest(state)
                        for motor in ('id','aligned'):
                            for j,pos in enumerate(a.STARTS):
                                execute(f'{label}/{motor}/start{j}',whole=state,position=pos,motor=motor)
                        for region in (0,1):
                            execute(f'{label}/probe/region{region}',whole=state,position=.25+.5*region,mode='probe',seconds=5)
                        assert a.digest(state)==before
                        bounded(); gc.collect()
                    a.save(folder/'complete.json',{'material':m['key'],'profile':profile,'stages':26})
        paths=list((a.WORK/'science').rglob('result.json'))
        assert len(paths)==312
        frozen_check()
        a.save(a.WORK/'science-complete.json',{'stages':len(paths),'materials':4,'profiles':3,
            'wall_seconds':sum(a.read(p)['wall_seconds'] for p in paths),
            'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        print(json.dumps(a.read(a.WORK/'science-complete.json')),flush=True)
    finally:
        lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('register','run'))
    args=parser.parse_args(); register() if args.command=='register' else run()
