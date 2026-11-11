"""Offline source-size planning only; no scientific subject or simulation engine."""
import argparse
import json
from pathlib import Path
import numpy as np


def plan():
    rng=np.random.default_rng(2026101691);rows=[]
    for n in (48,64,80,96,112,128):
        t=rng.random((20000,n))<.8
        c=t[:,:,None] & (rng.random((20000,n,4))<.75)
        positive=(t[:,:,None] & ~c).sum(axis=1)
        p=np.minimum(1.,2.**(1-positive))
        ordered=np.sort(p,axis=1)
        adjusted=np.maximum.accumulate(np.minimum(1.,ordered*np.array([4,3,2,1])),axis=1)
        power=float((adjusted<.05).all(axis=1).mean());se=(power*(1-power)/20000)**.5
        rows.append({'n':n,'joint_four_comparison_power':power,'mc95':[power-1.96*se,power+1.96*se]})
        if power>=.8:break
    return {'planning_only':True,'seed':2026101691,'simulations':20000,'family_comparisons':4,
            'test':'exact paired binary discordant sign / McNemar; Holm family correction',
            'assumption':{'threeMind_joint_pass':.8,'comparator_joint_pass':.6,
                          'positive_difference_probability':.2,'negative_difference_probability':0,
                          'paired_standardized_effect':.5},
            'scope':'Planning conditional on stated paired-outcome distribution; no new criterion or consciousness score; not observed scientific data.',
            'candidate_results':rows,'selected_n':next((r['n'] for r in rows if r['joint_four_comparison_power']>=.8),None)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    result=plan()
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
