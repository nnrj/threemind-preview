"""Numerical time-composition checks for candidate formulas, without any subject."""
import json
import math
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')
FAST=30/(-math.log2((.5-.2*2**(-30/300))/.8))
FUNCTIONS={'exponential':lambda t:2**(-t/30),'power':lambda t:1/(1+t/30),
           'inverse_log':lambda t:1/(1+math.log1p(t/(30/(math.e-1)))),
           'two_exponentials':lambda t:.8*2**(-t/FAST)+.2*2**(-t/300)}

def main():
    rows=[]
    for name,fn in FUNCTIONS.items():
        for steps in (1,2,10,60):
            dt=30/steps;naive=1.;age_aware=1.;age=0.
            for _ in range(steps):
                naive*=fn(dt)
                age_aware*=fn(age+dt)/fn(age);age+=dt
            assert abs(age_aware-fn(30))<1e-12
            rows.append(dict(curve=name,steps=steps,direct=fn(30),naive_reset_age=naive,age_aware=age_aware))
    separate=[]
    for steps in (1,2,10,60):
        fast,slow=.8,.2
        for _ in range(steps):fast*=2**(-30/steps/FAST);slow*=2**(-30/steps/300)
        assert abs(fast+slow-.5)<1e-12
        separate.append(dict(steps=steps,total=fast+slow,fast=fast,slow=slow))
    out=dict(classification='implementation mathematics; no subjects, no biological or behavioral result',
        question='Can candidate decay be advanced in arbitrary partitions without changing the result?',
        assumptions='no reinforcement; normalized initial value; all half-value times equal 30 seconds',
        finding='non-exponential functions cannot in general replace an exponential per-step multiplier while resetting age at each call',
        age_aware_composition_error_max=max(abs(x['age_aware']-x['direct']) for x in rows),
        values=rows,two_component_state=separate)
    with (WORK/'candidate-consistency-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,sort_keys=True)
    print(json.dumps(dict(max_age_aware_error=out['age_aware_composition_error_max'],ten_steps=[x for x in rows if x['steps']==10]),indent=2))

if __name__=='__main__':main()
