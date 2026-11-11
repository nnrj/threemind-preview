"""Analytic single-contribution lifetimes; no subject creation or advancement."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def lifetimes(weight,scale=30.,floor=.008):
    ratio=weight/floor
    assert ratio>1
    return {'exponential':scale*math.log2(ratio),
            'power-law':scale*(ratio-1),
            'inverse-logarithmic':scale*math.expm1(ratio-1)/math.expm1(1)}

def main(output):
    assert not output.exists();output.mkdir(parents=True)
    rows=[dict(initial_weight=w,seconds=lifetimes(w)) for w in (.01,.02,.05,.1,.2)]
    for row in rows:
        w=row['initial_weight']
        for curve,t in row['seconds'].items():
            age=t/30
            fraction={'exponential':lambda:2**(-age),'power-law':lambda:1/(1+age),
                      'inverse-logarithmic':lambda:1/(1+math.log1p(math.expm1(1)*age))}[curve]()
            assert math.isclose(w*fraction,.008,rel_tol=2e-14)
    receipt=dict(kind='analytic single-contribution comparison',scientific_n=0,scale_seconds=30.,deletion_floor=.008,
        assumptions=['One contribution at age zero','Constant decay timescale','No reinforcement or damage',
                     'Endpoints remain present; threshold time only, not a simulated deletion event'],rows=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'analytic-lifetimes.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    plt.rcParams.update({'font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(9.3,5.6),constrained_layout=True)
    weights=np.linspace(.0081,.2,300)
    for curve,color in (('exponential','#4267A9'),('power-law','#3C8555'),('inverse-logarithmic','#B05B29')):
        ax.plot(weights,[lifetimes(float(w))[curve]/86400 for w in weights],label=curve,color=color,lw=2)
    ax.axhline(30,ls='--',color='#666666',lw=1,label='30-day assay horizon')
    ax.set(xlabel='Initial weight of one contribution',ylabel='Days to reach weight 0.008',yscale='log',
           title='Same 30-s initial half-value scale; different threshold lifetimes')
    ax.grid(alpha=.2,which='both');ax.legend()
    fig.suptitle('Analytic comparison, not simulated subjects\nFixed timescale; no reinforcement/damage; endpoints remain',fontsize=11)
    for suffix in ('png','svg','pdf'):fig.savefig(output/f'analytic-lifetimes.{suffix}',dpi=180)
    plt.close(fig)
    print(json.dumps(receipt))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
