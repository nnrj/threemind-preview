"""Timing figure from immutable analysis, no subject loading."""
import argparse
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(work):
    a=json.loads((work/'analysis-v1.json').read_bytes()); s=a['summary']
    lags=[0,1,10,25,50,100]; x=np.arange(len(lags))
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),constrained_layout=True)
    for arm,color in [('normalized','#2563eb'),('summed','#d97706')]:
        observed=[s['groups'][f'XY-{lag}'][arm]['mean'] for lag in lags]
        predicted=[statistics.mean((1 if r['case']['history']==0 else -1)*r['forecast']['at_second_arrival']
                                   for r in a['rows'] if r['branch']['cue']==f'XY-{lag}' and r['branch']['arm']==arm) for lag in lags]
        axes[0].plot(x,observed,'o-',color=color,label=arm+' measured')
        axes[0].plot(x,predicted,'x--',color=color,alpha=.65,label=arm+' forecast')
    axes[0].set_ylabel('Opposite-history contrast / 2 at 110 + lag ms')
    axes[0].legend(frameon=False,fontsize=9)
    axes[0].set_title('Same total cue dose; varying timing')
    values=[s['prediction_mae_by_lag'][f'XY-{lag}'] for lag in lags]
    axes[1].bar(x,[v['mean'] for v in values],color='#475569')
    axes[1].errorbar(x,[v['mean'] for v in values],yerr=[[v['mean']-v['bootstrap_95'][0] for v in values],
                                                       [v['bootstrap_95'][1]-v['mean'] for v in values]],fmt='none',color='black',capsize=4)
    axes[1].set_ylabel('Mean absolute forecast error per origin')
    axes[1].set_title('All lags retained; pointwise origin intervals')
    for ax in axes:
        ax.set_xticks(x,[str(v) for v in lags]); ax.set_xlabel('Y delay after X (ms; categorical spacing)')
        ax.spines[['top','right']].set_visible(False); ax.grid(axis='y',alpha=.15)
    fig.suptitle('M2 timing pilot | 8 new origins, 288 nested causal copies | exploratory\nS mode; forecasts fixed before cues; no Core/default change',fontsize=13)
    target=work/'figure-v1.png'
    if target.exists():raise FileExistsError('preserve prior figure')
    fig.savefig(target,dpi=140); print(target)


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-timing-v1'))
    main(p.parse_args().work)
