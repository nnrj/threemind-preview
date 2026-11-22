"""Small formula tests for the isolated learning interventions; no teaching."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/'src'))
spec=importlib.util.spec_from_file_location('r51t15_component_engine',HERE/'research.py')
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)

def trial(mode,pos,neg):
    cfg=r.ResearchConfig(consolidation_mode='adaptive-half-life',novelty_mode='immediate',
        research_learning_component=mode,inhibition_updates_usage=False,retention_growth_enabled=True)
    engine=r.ResearchEngine(cfg);engine.time_us=100000
    timers=[];engine._edge_timer=lambda edge:timers.append(True)
    before={'weight':.2,'stability':.3,'eligibility':.4,'half_life':30.0,
        'fast':{'value':.2,'time_us':'0'},'touches':2,'last_touch_us':'0','last_pass_us':'0'}
    edge=SimpleNamespace(**deepcopy(before));engine._learn_component(edge,.2,pos,neg)
    return before,vars(edge),timers

expected={'none':set(),'weight':{'weight'},'fast':{'fast'},'eligibility':{'eligibility'},
          'stability':{'stability'},'retention':{'half_life'},'touch':{'touches','last_touch_us'}}
rows=[]
for mode,fields in expected.items():
    before,after,timers=trial(mode,0,.5)
    changed={k for k in before if before[k]!=after[k]}
    assert changed==fields,(mode,changed,fields)
    assert bool(timers)==bool(fields)
    rows.append({'mode':mode,'inhibitory_fields':sorted(changed)})
baseline=trial('none',.2,0)[1]
for mode in expected:assert trial(mode,.2,0)[1]==baseline,mode
print(json.dumps({'passed':True,'field_isolation_checks':len(rows),
    'excitatory_equivalence_checks':len(expected),'rows':rows}))
