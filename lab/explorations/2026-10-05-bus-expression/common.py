"""E49 shared registration and bounded read-only evidence access."""
import importlib.util,json,sys,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/bus-expression-20261005'
PREVIOUS=ROOT/'.work/temporal-state-20261005'
OLD=ROOT/'.work/expression-alignment-20261005'

def study(prepare=False):
    return Study(StudyConfig('bus-expression/1','E49 总线与表达器校准',HERE,WORK,48,
        instance_limit=256,wall_seconds=10800,storage_soft=2*2**30,storage_hard=8*2**30,
        usage_soft_delta=5,usage_hard_delta=8),prepare=prepare)

def guard(s,force=False):
    s.guard(force)
    if force or not hasattr(s,'extra'):
        s.extra=sum(read_json(p).get('wall_seconds',0) for p in (WORK/'timing').glob('*.json'))
    active=time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall+s.extra+active>s.settings.wall_seconds:raise RuntimeError('aggregate compute budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated()>3*2**30:raise RuntimeError('GPU memory budget')

def rows():
    # Cache created by E48, not re-normalized or modified here.
    with np.load(PREVIOUS/'raw-word-features.npz',allow_pickle=False) as data:
        meta=json.loads(str(data['metadata']))
        values=data['all'].copy();cross=data['cross'].copy()
    return [r|{'values':values[i],'cross':cross[i]} for i,r in enumerate(meta)]

def partitions(owner):
    own=[r for r in rows() if r['seed']==owner and r['modality']=='words']
    train=[r for r in own if r['split']=='train' and r['condition'] in ('continued','reversal') and r['seconds']==532 and r['item']>=0]
    test=[r for r in own if r['split']=='test']
    if len(train)!=16:raise ValueError('registered teaching partition changed')
    return train,test

def old_helpers():
    path=ROOT/'lab/explorations/2026-10-05-temporal-state-expression/experiment.py'
    spec=importlib.util.spec_from_file_location('e48_helpers',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def summary(details):
    groups={}
    for r in details:
        if r['item']<0:continue
        key=r['condition'],r['seconds']
        group=groups.setdefault(key,{'condition':key[0],'seconds':key[1],'correct':0,'count':0})
        group['count']+=1;group['correct']+=r['output']==r['target']
    return list(groups.values())

if __name__=='__main__':
    s=study(True)
    try:
        new_json(WORK/'usage.json',{'used_percent':48})
        new_json(WORK/'dependencies.json',{'E47':str(OLD),'E48':str(PREVIOUS),
            'E48_project':read_json(PREVIOUS/'platform.json')['project_id'],
            'E47_project':read_json(OLD/'platform.json')['project_id']})
        print({'project':s.project},flush=True)
    finally:s.db.close()
