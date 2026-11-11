import gzip,importlib.util,json,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import torch
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip
HERE=Path(__file__).resolve().parent;FIRST=ROOT/'.work/graph-expression-20261005';WORK=ROOT/'.work/graph-expression-v2-20261005'
E48=ROOT/'.work/temporal-state-20261005';E49=ROOT/'.work/bus-expression-20261005'
OLD=ROOT/'.work/expression-alignment-20261005'


def study(prepare=False):
    return Study(StudyConfig('graph-expression/2','E50 图与活动表达修订、共同所指',HERE,WORK,49,
        instance_limit=384,wall_seconds=14400,storage_soft=3*2**30,storage_hard=8*2**30,
        usage_soft_delta=6,usage_hard_delta=10),prepare=prepare)


def guard(s,force=False):
    s.guard(force)
    if force or not hasattr(s,'extra'):
        s.extra=sum(read_json(p).get('wall_seconds',0) for p in (WORK/'timing').glob('*.json'))
        s.first_wall=sum(read_json(p).get('wall_seconds',0) for p in (FIRST/'cases').glob('*/result.json'))+sum(read_json(p).get('wall_seconds',0) for p in (FIRST/'timing').glob('*.json'))
        s.first_cases=len(list((FIRST/'cases').glob('*/result.json')))
    active=time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall+s.extra+s.first_wall+active>s.settings.wall_seconds:raise RuntimeError('total compute budget')
    if s.completed_count+s.first_cases>=s.settings.instance_limit:raise RuntimeError('combined instance budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated()>3*2**30:raise RuntimeError('GPU budget')


def helpers():
    spec=importlib.util.spec_from_file_location('e48_graph_helpers',ROOT/'lab/explorations/2026-10-05-temporal-state-expression/experiment.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def process(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def scores(rows,keys=('condition','seconds')):
    groups={}
    for row in rows:
        if row['item']<0:continue
        key=tuple(row.get(k) for k in keys);group=groups.setdefault(key,{k:v for k,v in zip(keys,key)}|{'correct':0,'count':0})
        group['count']+=1;group['correct']+=row['output']==row['target']
    return list(groups.values())


if __name__=='__main__':
    s=study(True)
    try:
        new_json(WORK/'usage.json',{'used_percent':49})
        new_json(WORK/'dependencies.json',{name:{'path':str(path),'project_id':read_json(path/'platform.json')['project_id']} for name,path in [('E48',E48),('E49',E49),('E47',OLD)]})
        new_json(WORK/'previous-phase.json',{'path':str(FIRST),'project_id':read_json(FIRST/'platform.json')['project_id'],'shared_budgets':True})
        for language in ('zh','en'):
            s.note('instrument-revision:'+language,'E50 工具修订 / Instrument revision '+language,(HERE/f'revision.{language}.md').read_text(encoding='utf-8'))
        print({'project':s.project},flush=True)
    finally:s.db.close()
