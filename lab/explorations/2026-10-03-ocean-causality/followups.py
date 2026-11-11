"""One serial follow-up chain per world, after its random control frees a slot."""
import argparse
import time
from experiment import WORK,study,simulation_budget
from lab.tools.ocean_cli import read_json,write_json
from closed_loop import execute as closed
from endpoint import execute as endpoint
from probe import run as probe
from birth_probe import execute as balanced
from analyze_probes import analyze

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1),required=True);a=p.parse_args();g=a.group
    before=WORK/'cases'/f'g{g}-random-fast'/'result.json'
    while not before.exists():time.sleep(2)
    result=read_json(before)
    if result['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError(result)
    s=study()
    try:simulation_budget(s)
    finally:s.db.close()
    for op in ('sham','target','matched','history-strength-zero'):
        closed(g,op)
        r=read_json(WORK/'closed-loop'/f'g{g}-{op}'/'result.json')
        if r['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError(r['error'] or r['status'])
    balanced(g,200)
    endpoint(g)
    probe(f'g{g}-core',600)
    analyze(WORK/'probes'/f'g{g}-core-600')
    balanced(g,600)
    write_json(WORK/f'followups-{g}.json',{'status':'complete'})
