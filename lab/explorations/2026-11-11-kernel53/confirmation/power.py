"""Prospective planning, standardized paired effect 0.5, three comparisons."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import t

def compute():
    n, simulations, effect, alpha = 48, 50000, 0.5, .05/3
    rng=np.random.default_rng(261111053)
    differences=rng.normal(effect,1,(simulations,n))
    statistic=differences.mean(axis=1)/(differences.std(axis=1,ddof=1)/np.sqrt(n))
    critical=float(t.ppf(1-alpha,n-1))
    power=float((statistic>critical).mean())
    return dict(n=n,simulations=simulations,seed=261111053,paired_standardized_effect=effect,
                family_alpha=.05,comparisons=3,one_sided_alpha=alpha,critical_t=critical,power=power,
                monte_carlo_se=float(np.sqrt(power*(1-power)/simulations)),
                model='Independent normal paired differences; continuous mean late history-RMS endpoint',
                use='Planning assumption, not a guarantee for every non-normal population or binary target')

if __name__=='__main__':
    result=compute();assert result['power']>=.8
    with Path(__file__).with_name('power.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
