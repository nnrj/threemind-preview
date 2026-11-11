"""Prospective M4 whole subject with immutable, verified external training data.

This is a new research-state schema, not a replacement for the frozen N0 or E69
schemas. All personal weights, Adam/RNG, history and physical states remain in
the whole checkpoint. File operations never step the subject.
"""
import copy
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import torch

from m4_instrument import Whole, Executor, digest
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.continuous_foveal_motor import ContinuousFovealMotor
from lab.tools.sensorimotor_session import SensorimotorSession

SCHEMA='threemind.regional-eye-hand-whole/2'
ARRAYS=('x','eye','hand','move')


class Subject(Whole):
    def __init__(self,seed,*,identity,data_root):
        super().__init__(seed,identity=identity)
        self.data_root=Path(data_root).resolve()

    def dependency(self,ref):
        name=Path(ref['path'])
        if name.is_absolute() or name.drive:raise ValueError('relative corpus path required')
        path=(self.data_root/name).resolve()
        if not path.is_relative_to(self.data_root):raise ValueError('corpus escapes subject data root')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('corpus bytes changed')
        return path

    def verify_dependencies(self):
        for ref in self.corpus:
            path=self.dependency(ref)
            with np.load(path,allow_pickle=False) as z:
                if set(z.files)!=set(ARRAYS):raise ValueError('corpus array contract')
                if not all(len(z[k])==ref['examples'] for k in ARRAYS):raise ValueError('corpus count')
                if z['x'].shape[1:]!=(8,self.motor.layout.width):raise ValueError('corpus input layout')

    def add_samples(self,name,values,*,metadata):
        """External teacher labels are stored separately from inference input."""
        if not name or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz-_' for c in name):
            raise ValueError('simple immutable corpus name')
        if set(values)!=set(ARRAYS):raise ValueError('corpus array names')
        arrays={'x':np.asarray(values['x'],dtype=np.float32)}
        count=len(arrays['x'])
        if not 1<=count<=512 or arrays['x'].shape!=(count,8,self.motor.layout.width):raise ValueError('bounded raw corpus')
        for k in ARRAYS[1:]:arrays[k]=self.motor._targets(values[k],count,k)
        if any(arrays[k].shape!=(count,) for k in ARRAYS[1:]):raise ValueError('aligned teacher targets')
        receptors=len(self.motor.centers)
        if np.any((arrays['eye']<0)|(arrays['eye']>=receptors)) or np.any((arrays['move']<0)|(arrays['move']>1)):
            raise ValueError('eye or movement target outside output range')
        if np.any((arrays['hand'] < -1)|(arrays['hand']>=receptors)) or np.any((arrays['move']==1)&(arrays['hand']<0)):
            raise ValueError('hand target inconsistent with movement')
        if not np.isfinite(arrays['x']).all():raise ValueError('nonfinite raw data')
        if sum(r['examples'] for r in self.corpus)+count>4096:raise ValueError('registered corpus capacity')
        if any(r['path']==f'corpus/{name}.npz' for r in self.corpus):raise FileExistsError(name)
        before=self.session.engine.time_us
        stream=io.BytesIO();np.savez_compressed(stream,**arrays);body=stream.getvalue()
        path=self.data_root/'corpus'/f'{name}.npz';path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as out:out.write(body)
        ref={'path':path.relative_to(self.data_root).as_posix(),'sha256':hashlib.sha256(body).hexdigest(),
             'examples':count,'metadata':copy.deepcopy(metadata)}
        self.corpus.append(ref)
        assert self.session.engine.time_us==before
        return copy.deepcopy(ref)

    def training_arrays(self):
        self.verify_dependencies();chunks={k:[] for k in ARRAYS}
        for ref in self.corpus:
            with np.load(self.dependency(ref),allow_pickle=False) as z:
                for k in ARRAYS:chunks[k].append(z[k])
        if not chunks['x']:raise ValueError('empty training corpus')
        return {k:np.concatenate(v,axis=0) for k,v in chunks.items()}

    def state(self):
        return super().state()|{'schema':SCHEMA,'corpus_storage':'immutable-relative-npz/1'}

    def save(self,folder):
        self.verify_dependencies();folder=Path(folder);part=folder.with_name(folder.name+'.partial')
        if folder.exists():raise FileExistsError(folder)
        part.mkdir(parents=True,exist_ok=False)
        before=self.session.engine.time_us
        raw=json.dumps(self.state(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        (part/'system.json.gz').write_bytes(gzip.compress(raw,compresslevel=1,mtime=0))
        self.motor.save(part/'motor');self.words.save(part/'words')
        files={p.relative_to(part).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in part.rglob('*') if p.is_file()}
        (part/'complete.json').write_text(json.dumps({'schema':SCHEMA,'canonical_sha256':digest(self.canonical()),
            'files':files,'time_us':before,'identity':self.identity,'dependencies':copy.deepcopy(self.corpus)},sort_keys=True),encoding='utf-8')
        if self.session.engine.time_us!=before:raise RuntimeError('save advanced internal time')
        part.rename(folder)

    @classmethod
    def restore(cls,folder,*,data_root):
        folder=Path(folder).resolve();r=json.loads((folder/'complete.json').read_bytes())
        if r['schema']!=SCHEMA:raise ValueError('not prospective M4 whole schema')
        for name,sha in r['files'].items():
            path=(folder/name).resolve()
            if not path.is_relative_to(folder) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
                raise ValueError('whole checkpoint integrity')
        v=json.loads(gzip.decompress((folder/'system.json.gz').read_bytes()))
        if v['schema']!=SCHEMA or v['corpus_storage']!='immutable-relative-npz/1' or v['corpus']!=r['dependencies']:
            raise ValueError('whole corpus contract')
        a=cls.__new__(cls);a.data_root=Path(data_root).resolve()
        for name in ('identity','seed','text_seed','phase','cursor','corpus','branch'):setattr(a,name,v[name])
        # Verify dependency bytes before constructing the saved subject.
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
