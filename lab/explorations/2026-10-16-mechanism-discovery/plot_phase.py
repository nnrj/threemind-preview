"""Scientific figure from saved analysis only; no organism loading."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(work):
    a=json.loads((work/'analysis-v1.json').read_bytes());s=a['summary']
    phases=[7,43,87,99];lags=[0,1,2,20,80]
    fig,axes=plt.subplots(1,3,figsize=(15,5.2),constrained_layout=True)
    vmax=max(s['groups'][f'p{p}-d{d}'][arm]['mean'] for p in phases for d in lags for arm in ['normalized','summed'])
    for ax,arm in zip(axes[:2],['normalized','summed']):
        values=np.array([[s['groups'][f'p{p}-d{d}'][arm]['mean'] for d in lags] for p in phases])
        im=ax.imshow(values,vmin=0,vmax=vmax,cmap='Blues',aspect='auto')
        for i,p in enumerate(phases):
            for j,d in enumerate(lags):
                ax.text(j,i,f'{values[i,j]:.4f}'+('*' if p+d>100 else ''),ha='center',va='center',
                        color='white' if values[i,j]>.6*vmax else '#111827',fontsize=8)
        ax.set_xticks(range(5),lags);ax.set_yticks(range(4),phases)
        ax.set_xlabel('Y lag after X (ms)');ax.set_ylabel('X phase after parent boundary (ms)')
        ax.set_title(arm+' | first 110ms contrast')
    fig.colorbar(im,ax=axes[:2],shrink=.8,label='Mean opposite-history contrast / 2')
    for i,(model,color) in enumerate([('phase-aware','#2563eb'),('all-same-cycle','#d97706')]):
        vals=list(s['prediction_mae_by_origin'][model].values())
        axes[2].scatter(np.linspace(i-.13,i+.13,len(vals)),vals,color=color,label=model)
        desc=s['primary_prediction_mae'][model]
        axes[2].errorbar(i,desc['mean'],yerr=[[desc['mean']-desc['bootstrap_95'][0]],
                                           [desc['bootstrap_95'][1]-desc['mean']]],fmt='ks',capsize=5)
    axes[2].set_xticks([0,1],['phase-aware','all-same-cycle']);axes[2].set_yscale('log')
    axes[2].set_ylabel('Mean absolute error per independent origin')
    axes[2].set_title('Frozen forecasts; points = 8 origins')
    axes[2].axhline(1e-6,color='#64748b',ls=':',label='prespecified 1e-6 tolerance')
    axes[2].legend(frameon=False,fontsize=8);axes[2].grid(axis='y',alpha=.2)
    fig.suptitle('M2 phase pilot | 8 new origins, 672 nested copies | exploratory\n* Y crosses the 100ms emission boundary; original timing failure remains unchanged',fontsize=12)
    target=work/'figure-v1.png'
    if target.exists():raise FileExistsError('preserve prior figure')
    fig.savefig(target,dpi=150);print(target)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    main(p.parse_args().work)
