"""Figures from completed recordings only; no engine construction or simulation."""
import argparse
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as h
import body as b
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def save(fig,folder,name):
    folder.mkdir(exist_ok=True)
    for suffix in ('png','svg','pdf'):fig.savefig(folder/(name+'.'+suffix),dpi=180,bbox_inches='tight')
    plt.close(fig)

def mechanisms(work):
    assert h.read(work/'audit.json')['passed']
    old=work.parent/'persistent-activity61-v1';table=h.read(work/'cases.json')
    fig,axes=plt.subplots(1,3,figsize=(13.5,3.7))
    refs=[(old,'v61','6.1 reference'),(work,'persist-g0.24-t0.25','Shorter inhibition'),(work,'persist-g0.015-t0.25','Weaker, shorter inhibition')]
    for root,var,label in refs:
        cc=h.read(root/'cases.json')
        c=next(c for c in cc if c['variant']==var and c['kind']=='readout_wait' and c['material_key']=='readout/s0/011/paired/d300/wait')
        points=h.e.unpacked(root/'cases'/c['key']/'trajectory.json.xz')['points']
        axes[0].plot([(p['time_us']-c['begin_us'])/1e6 for p in points],[max((n['activation'] for n in p['nodes']),default=0) for p in points],label=label,lw=1.3)
    axes[0].set(xlabel='Time after teaching (s)',ylabel='Maximum task activation',title='A  Persistence with inhibition retained',ylim=(-.025,1.025))
    axes[0].legend(fontsize=8)
    ids=h.e.materials.TOKENS
    for cue,color in [('AB','#1565c0'),('DB','#c0392b')]:
        c=next(c for c in table if c['variant']=='prefix-immediate-no-inhibitory-learning' and c['block']==0 and c.get('cue')==cue)
        points=h.e.unpacked(work/'cases'/c['key']/'trajectory.json.xz')['points']
        pts=[p for p in points if 0<=p['time_us']-c['probe_start_us']<=3000000]
        val=lambda p,k:next((n['activation'] for n in p['nodes'] if n['channel']==ids[k]),0.)
        ts=[(p['time_us']-c['probe_start_us'])/1e6 for p in pts]
        axes[1].plot(ts,[val(p,'A')-val(p,'D') for p in pts],label=cue,color=color)
        axes[2].plot(ts,[val(p,'C')-val(p,'E') for p in pts],label=cue,color=color,ls='-' if cue=='AB' else '--')
    for ax in axes[1:]:ax.axvline(1,color='gray',ls=':',lw=1);ax.axhline(0,color='gray',lw=.7);ax.set_xlabel('Time from prefix (s)');ax.legend(fontsize=8)
    axes[1].set(title='B  Prefix difference remains',ylabel='Activation A minus D')
    axes[2].set(title='C  Endings retain the same preference',ylabel='Activation C minus E')
    fig.tight_layout();save(fig,work/'figures','persistence-and-prefix')

def body(work):
    assert h.read(work/'audit.json')['passed'];cases=h.read(work/'cases.json');seed=b.SEEDS[0];ids=b.mapping(seed)
    fig,axes=plt.subplots(1,2,figsize=(11,3.8))
    value=lambda p,ch:next((n['activation'] for n in p['nodes'] if n['channel']==ch),0.)
    for t,color in [(.0004,'#1565c0'),(.004,'#c0392b')]:
        get=lambda sign:next(c for c in cases if c['kind']=='static' and c['seed']==seed and c['mode']=='full' and c['threshold']==t and c['sign']==sign)
        probe=b.e.unpacked(work/'cases'/get(1)['key']/'trajectory.json.xz');blank=b.e.unpacked(work/'cases'/get(0)['key']/'trajectory.json.xz')
        start=probe[0]['time_us'];x=[(p['time_us']-start)/1e6 for p in probe]
        y=[value(p,ids['A'])-value(p,ids['B'])-value(z,ids['A'])+value(z,ids['B']) for p,z in zip(probe,blank)]
        axes[0].plot(x,y,label=str(t),color=color)
    axes[0].axhline(0,color='gray',lw=.7);axes[0].set(xlabel='Time from probe (s)',ylabel='Blank-subtracted A minus B',title='A  Same taught state, opposite preferences');axes[0].legend(title='Threshold',fontsize=8)
    series=[('core',.0004,'Full, 0.0004','#1565c0'),('core',.004,'Full, 0.004','#c0392b'),('zero',.0004,'Zero torque','#757575'),('pd',.0004,'PD reference','#2e7d32')]
    for ctl,t,label,color in series:
        c=next(c for c in cases if c['kind']=='body' and c['seed']==seed and c['mode']=='full' and c['controller']==ctl and c['threshold']==t and c['polarity']==1 and c['sign']==1)
        pts=[p for p in b.e.unpacked(work/'cases'/c['key']/'trajectory.json.xz') if 'q' in p];start=pts[0]['time_us']
        axes[1].plot([(p['time_us']-start)/1e6 for p in pts],[p['q'] for p in pts],label=label,color=color,lw=1.3)
    axes[1].axvspan(4,4.2,color='gray',alpha=.2);axes[1].axhline(0,color='gray',lw=.7)
    axes[1].set(xlabel='Body time (s)',ylabel='Joint angle (rad)',title='B  Fixed motor rule does not stabilize');axes[1].legend(fontsize=8)
    fig.tight_layout();save(fig,work/'figures','reversal-and-posture')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('mechanisms','body'));p.add_argument('work',type=Path)
    a=p.parse_args();globals()[a.kind](a.work)
