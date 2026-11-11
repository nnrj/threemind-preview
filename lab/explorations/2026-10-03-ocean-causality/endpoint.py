"""Separate short continuation for pre-registered 600 s causal probes."""
import argparse
import json
from experiment import WORK,study,simulation_budget
from lab.tools.ocean_contact_cli import load,run

def execute(group):
    s=study()
    try:
        key=f'g{group}-core'
        world=load(WORK/'cases'/key/'final')
        r=run(world,WORK/'evaluations'/f'{key}-600',20,guard=lambda:simulation_budget(s),wall_seconds=300,checkpoint_s=1000)
        print(json.dumps({'case':key,'status':r['status'],'wall_seconds':r['wall_seconds']}),flush=True)
    finally:s.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1),required=True);a=p.parse_args()
    execute(a.group)
