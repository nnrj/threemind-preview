"""Short, same-world causal forks after measured local effects; all originals retained."""
import argparse
import json
import time
from experiment import WORK,study,simulation_budget
from lab.tools.ocean_contact_cli import load,run
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_causality import neutralize_persistent_strength
from threemind_runtime import create_engine


def execute(group,operation):
    source=WORK/'cases'/f'g{group}-core'/'checkpoints'/'200000000'
    probe=read_json(WORK/'probes'/f'g{group}-core-200'/'summary.json')
    plans={r['individual']:r['plan'] for r in probe['individuals'] if r['plan']['applicable']}
    world=load(source)
    receipt={'source':str(source.relative_to(WORK)),'operation':operation,'targets':{},
             'meaning':'same awake world; finite energy and ordinary learning retained; no donor selection by benefit'}
    for i,body in world.bodies.items():
        if not body.physical:continue
        plan=plans.get(i)
        if plan is None and operation!='history-strength-zero':continue
        if operation in ('target','matched'):
            edges=plan[operation+'_edges']
            world.engines[i].intervene(edges=edges,action='silence')
            receipt['targets'][i]=edges
        elif operation=='history-strength-zero':
            world.engines[i]=create_engine(state=neutralize_persistent_strength(world.engines[i].capture_state()),backend='native')
            receipt['targets'][i]='persistent node/edge strengths zero; topology and fast/physical states retained'
        elif operation=='restore':
            edges=plan['target_edges']
            world.engines[i].intervene(edges=edges,action='silence')
            world.engines[i].intervene(edges=edges,action='unsilence')
        elif operation!='sham':raise ValueError(operation)
    folder=WORK/'closed-loop'/f'g{group}-{operation}'
    s=study()
    try:
        r=run(world,folder,60,guard=lambda:simulation_budget(s),wall_seconds=600,checkpoint_s=1000)
        write_json(folder/'intervention.json',receipt)
        print(json.dumps({'operation':operation,'group':group,'status':r['status'],'wall_seconds':r['wall_seconds'],
            'food':sum(m['grains'] for m in r['members']),'predations':r['totals']['predations']}),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1),required=True)
    p.add_argument('--operation',choices=('sham','target','matched','history-strength-zero','restore'),required=True)
    a=p.parse_args();execute(a.group,a.operation)
