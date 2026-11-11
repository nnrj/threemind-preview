"""M4 new whole-state file encoding; canonical subject state is unchanged."""
import copy,hashlib,json
from dataclasses import asdict
from pathlib import Path
import torch
from safetensors.torch import load_file
from m4_subject import Subject as PlainSubject,SCHEMA
from m4_instrument import Executor,digest,tensor_tree
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.continuous_foveal_motor import ContinuousFovealMotor
from lab.tools.sensorimotor_session import SensorimotorSession
import m4_compact_evidence_v2 as codec


class Subject(PlainSubject):
    def save(self,folder):
        self.verify_dependencies();folder=Path(folder);part=folder.with_name(folder.name+'.partial')
        if folder.exists():raise FileExistsError(folder)
        part.mkdir(parents=True,exist_ok=False)
        before=self.session.engine.time_us;canonical_sha=digest(self.canonical())
        codec.write(part/'system.json.xz',self.state())
        self.motor.save(part/'motor');self.words.save(part/'words')
        files={p.relative_to(part).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in part.rglob('*') if p.is_file()}
        (part/'complete.json').write_text(json.dumps({'schema':SCHEMA,'storage_schema':codec.SCHEMA,
            'canonical_sha256':canonical_sha,'files':files,'time_us':before,'identity':self.identity,
            'dependencies':copy.deepcopy(self.corpus)},sort_keys=True),encoding='utf-8')
        assert self.session.engine.time_us==before and digest(self.canonical())==canonical_sha
        part.rename(folder)

    @classmethod
    def restore(cls,folder,*,data_root):
        folder=Path(folder).resolve();r=json.loads((folder/'complete.json').read_bytes())
        if r['schema']!=SCHEMA or r['storage_schema']!=codec.SCHEMA:raise ValueError('compact whole schema')
        verify_files(folder,r)
        v=codec.read(folder/'system.json.xz')
        if v['schema']!=SCHEMA or v['corpus_storage']!='immutable-relative-npz/1' or v['corpus']!=r['dependencies']:
            raise ValueError('whole corpus contract')
        a=cls.__new__(cls);a.data_root=Path(data_root).resolve()
        for name in ('identity','seed','text_seed','phase','cursor','corpus','branch'):setattr(a,name,v[name])
        for ref in a.corpus:a.dependency(ref)
        a.session=SensorimotorSession(state=v['session'],dt_us=v['session']['dt_us'],backend='native')
        a._text_mapping();s=a.session
        if list(s.layout.channels)!=v['layout'] or asdict(s.sensor.config)!=v['sensor']:raise ValueError('restoration mapping')
        s.history.extend(v['history']);s.current=v['current'];s.stream.published=v['published']
        with torch.random.fork_rng(devices=[]):
            a.motor=ContinuousFovealMotor.restore(folder/'motor',device='cpu',expected_identity=a.identity)
            a.words=CalibratedActivity.restore(folder/'words',device='cpu')
        a.executor=Executor.restore(v['executor']);a.verify_dependencies()
        if a.words.identity!=a.identity or a.motor.layout.channels!=s.layout.channels or a.words.layout.channels!=s.layout.channels:
            raise ValueError('restored personal peripheral')
        if digest(a.canonical())!=r['canonical_sha256']:raise ValueError('whole restoration differs')
        return a


def verify_files(folder,receipt):
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}-{'complete.json'}
    if actual!=set(receipt['files']):raise ValueError('whole membership')
    for name,sha in receipt['files'].items():
        p=(folder/name).resolve()
        if not p.is_relative_to(folder.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise ValueError('whole integrity')


def stored_canonical(folder):
    """Independent file reconstruction; never instantiate an engine/subject."""
    r=json.loads((folder/'complete.json').read_bytes());verify_files(folder,r)
    assert r['storage_schema']==codec.SCHEMA
    result=codec.read(folder/'system.json.xz')
    for name in ('motor','words'):
        meta=json.loads((folder/name/'manifest.json').read_bytes())
        learning=torch.load(folder/name/'learning.pt',map_location='cpu',weights_only=True)
        result[name]={'weights':tensor_tree(load_file(str(folder/name/'model.safetensors'))),
                      'optimizer':tensor_tree(learning['optimizer']),'rng':tensor_tree(learning['rng']),
                      'computed':meta['computed_updates'],'committed':meta['committed_updates'],'training':False,
                      'identity':meta['identity'],'seed':meta['seed']}
    assert digest(result)==r['canonical_sha256'] and result['identity']==r['identity']
    assert int(result['session']['core']['time_us'])==r['time_us']
    return result,r
