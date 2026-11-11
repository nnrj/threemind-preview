"""Read-only confirmation tables, figure and pre-publication storage inventory."""
import argparse
import ctypes
from ctypes import wintypes
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pilot_m2 as m


def total(rows):
    return {'correct':sum(r['correct'] for r in rows),'n':sum(r['n'] for r in rows)}


def build(analysis):
    units=[u['summary'] for u in analysis['units']]
    tables={}
    for head in ('full','ports'):
        rows=[r for u in units for r in u['rows'] if r['head']==head]
        first={arm:{group:total([r['arms'][arm][group] for r in rows]) for group in ('new','old')}
               for arm in ('sham','target','matched','restored','plasticity-off')}
        joint={arm:{group:total([r['joint_cues'][arm][group] for r in rows]) for group in ('new','old')}
               for arm in first}
        heldout={kind:{group:total([r['heldout'][kind][group] for r in rows]) for group in ('new','old')}
                 for kind in ('fixed','continued')}
        early={group:total([r['early_'+group] for r in rows]) for group in ('new','old')}
        crosses={f'{reader}/{activity}/{group}':total([r for u in units for r in u['crosses']
                    if r['head']==head and r['reader_time']==reader and r['activity_time']==activity and r['group']==group])
                 for reader in ('early','late') for activity in ('early','late') for group in ('new','old')}
        assert all(first[arm][group]['n']==384 and joint[arm][group]['n']==192 for arm in first for group in ('new','old'))
        assert all(heldout[k][group]['n']==768 for k in heldout for group in ('new','old'))
        tables[head]={'first':first,'joint':joint,'heldout':heldout,'early':early,'crosses':crosses}
    sensory={group:total([r[group] for u in units for r in u['sensory'].values()]) for group in ('new','old')}
    return {'schema':'threemind.m5-confirmation-tables/1','independent_origins':48,'tables':tables,'sensory':sensory,
            'restoration_max_error':max(r['restoration_error'] for u in units for r in u['rows']),
            'secondary_only':True,'baseline_note':'192 unique singleton baseline questions per group, scored under two subsequent histories; not 384 independent questions.'}


def figure(analysis,summary,path):
    if path.exists():raise FileExistsError(path)
    fig,axes=plt.subplots(1,3,figsize=(16,5),constrained_layout=True)
    arms=['sham','target','matched','restored','plasticity-off']
    labels=['Sham','New path\nsilenced','Old path\nsilenced','Restored','Plasticity\nbundle off']
    xs=np.arange(5)
    for i,group in enumerate(('new','old')):
        vals=[summary['tables']['ports']['first'][arm][group] for arm in arms]
        bars=axes[0].bar(xs+(i-.5)*.38,[100*v['correct']/v['n'] for v in vals],.38,
                         color=('#2563eb','#e87924')[i],label=group.title()+' associations')
        for bar,value in zip(bars,vals):
            height=bar.get_height()
            axes[0].text(bar.get_x()+bar.get_width()/2, height-3 if height else 2,
                         f"{value['correct']}/{value['n']}",ha='center',
                         va='top' if height else 'bottom',rotation=90 if height else 0,
                         fontsize=8,color='white' if height else 'black')
    axes[0].set_xticks(xs,labels,fontsize=8);axes[0].set_ylim(0,120)
    axes[0].set_title('Fixed port reader: causal dissociation');axes[0].set_ylabel('Correct singleton answers (%)')
    axes[0].legend(fontsize=8,loc='upper center',ncol=2)
    keys=list(analysis['goals'])
    means=[analysis['goals'][k]['mean_difference'] for k in keys]
    ci=np.array([analysis['goals'][k]['bootstrap_observed_source_95'] for k in keys]).T
    bars=axes[1].bar(range(3),np.array(means)*100,color='#0d9488')
    axes[1].errorbar(range(3),np.array(means)*100,yerr=np.vstack((means-ci[0],ci[1]-means))*100,
                     fmt='none',ecolor='black',capsize=4)
    axes[1].bar_label(bars,labels=[f"{analysis['goals'][k]['qualifying_origins']}/48 qualify" for k in keys],fontsize=9,padding=5)
    axes[1].set_xticks(range(3),['Fixed\nexpression','Pathway\ndissociation','Readout\nscope'])
    axes[1].set_ylim(0,120);axes[1].set_title('Preregistered source-level effects')
    axes[1].set_ylabel('Mean paired difference (percentage points)')
    vals=[summary['tables'][h]['heldout'][k]['new'] for h in ('full','ports') for k in ('fixed','continued')]
    bars=axes[2].bar(range(4),[100*v['correct']/v['n'] for v in vals],color=['#64748b']*2+['#2563eb']*2)
    axes[2].bar_label(bars,labels=[f"{v['correct']}/{v['n']}" for v in vals],fontsize=9,padding=3)
    axes[2].set_xticks(range(4),['All: fixed','All:\ncontinued','Ports: fixed','Ports:\ncontinued'],fontsize=9)
    axes[2].set_ylim(0,120);axes[2].set_title('Secondary: held-out-dose expression')
    fig.suptitle('M5 independent confirmation | 48 new origins, paired histories | 6 dose/delay strata',fontsize=13)
    fig.savefig(path,dpi=160);plt.close(fig)


class StandardInfo(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),
              ('NumberOfLinks',wintypes.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]


def inventory(work):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    files=[p for p in work.rglob('*') if p.is_file() and p.name!='storage-inventory-v1.json']
    logical=allocated=unique_logical=0;seen=set();size=[]
    for p in files:
        st=p.stat();logical+=st.st_size
        key=(st.st_dev,st.st_ino)
        if key not in seen:
            handle=kernel.CreateFileW(str(p),0x80,7,None,3,0,None)
            if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            info=StandardInfo()
            try:
                if not kernel.GetFileInformationByHandleEx(handle,1,ctypes.byref(info),ctypes.sizeof(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:kernel.CloseHandle(handle)
            assert info.EndOfFile==st.st_size
            seen.add(key);unique_logical+=st.st_size;allocated+=info.AllocationSize
        if 'units' in p.parts and p.name.endswith('.json.gz'):size.append(st.st_size)
    return {'schema':'threemind.file-storage-inventory/1','phase':'before publication archive and API readback',
            'files':len(files),'logical_bytes':logical,'unique_files':len(seen),
            'hardlink_deduplicated_logical_bytes':unique_logical,'allocated_file_stream_bytes':allocated,
            'duplicate_hardlink_entries':len(files)-len(seen),'science_whole_snapshots':len(size),
            'snapshot_compressed_bytes':{'min':min(size),'median':statistics.median(size),'max':max(size)},
            'exclusions':'This inventory itself, later report copies/archive/readback, directory/MFT/database overhead. Allocation uses Windows FileStandardInfo, not rounded logical estimates.'}


def scale(work):
    rows=[]
    for origin in range(48):
        folder=work/'units'/f'o{origin}'
        parent=json.loads(gzip.decompress((folder/'h0-plasticity-True-taught.json.gz').read_bytes()))
        end=json.loads(gzip.decompress((folder/'h0-heldout-continued-0.96-q11.json.gz').read_bytes()))
        rows.append({'origin':origin,'parent_seconds':parent['time_us']/1e6,'final_seconds':end['time_us']/1e6,
                     'parent_nodes':len(parent['core']['nodes']),'parent_edges':len(parent['core']['edges']),
                     'end_nodes':len(end['core']['nodes']),'end_edges':len(end['core']['edges'])})
    return {'origins':rows,'identity':'Whole simulated individuals; branch lifetimes are not summed as one continuous lifetime.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);work=p.parse_args().work
    assert m.read(work/'status.json')['state']=='awaiting-analysis' and m.read(work/'audit-v1.json')['passed']
    analysis=m.read(work/'analysis-v1.json');summary=build(analysis)
    summary['scale']=scale(work)
    m.original(work/'summary-v1.json',summary)
    figure(analysis,summary,work/'figure-v1.png')
    storage=inventory(work);m.original(work/'storage-inventory-v1.json',storage)
    print(json.dumps({'summary':summary,'storage':storage}))
