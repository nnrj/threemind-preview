"""Prospectively enlarged pathway control, after the small-cut result."""
import argparse
import json
import time
from experiment import WORK,study,simulation_budget
from probe import records
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_contact_cli import load,run
from lab.tools.ocean_causality import select_pathways
from collections import defaultdict

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1),required=True);a=p.parse_args();g=a.group
    while not (WORK/f'followups-{g}.json').exists():time.sleep(2)
    original=WORK/'cases'/f'g{g}-core';recent=defaultdict(set)
    for row in records(original,199000000,200000000):
        for x in row['inputs']:recent[x['individual']].update(c for c,v in zip(x['channels'],x['values']) if v)
    s=study()
    try:
        for operation in ('region','region-matched'):
            world=load(original/'checkpoints/200000000');receipt={}
            for i,b in world.bodies.items():
                if not b.physical:continue
                plan=select_pathways(world.engines[i].capture_state(),recent[i],maximum=128,include_internal=True)
                receipt[i]=plan
                if plan['applicable']:
                    world.engines[i].intervene(edges=plan['target_edges' if operation=='region' else 'matched_edges'],action='silence')
            folder=WORK/'closed-loop'/f'g{g}-{operation}'
            result=run(world,folder,60,guard=lambda:simulation_budget(s),wall_seconds=600,checkpoint_s=1000)
            write_json(folder/'intervention.json',receipt)
            print(json.dumps({'group':g,'operation':operation,'status':result['status'],'wall_seconds':result['wall_seconds']}),flush=True)
            if result['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError(result['status'])
    finally:s.db.close()
