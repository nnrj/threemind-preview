"""Read-only paired analysis, explicit denominators and reproducible figures."""
import csv
import math
from collections import defaultdict
import apparatus as a
import study

STATES = ('blank','parent','newborn','redeveloped')

def integrals(rows):
    channels=defaultdict(float)
    associative=0.
    for row in rows:
        for n in row['nodes']:
            channels[str(n['channel'])] += .1*n['activation']
            associative += .1*n['associative']
    return dict(channels),associative

def distance(x,y):
    return sum(abs(x.get(k,0.)-y.get(k,0.)) for k in x.keys()|y.keys())

def edges(core):
    lookup={n['id']:n['channel'] for n in core['nodes']}
    return {(lookup[e['source']],lookup[e['target']]):e['weight'] for e in core['edges']}

def csv_write(name,rows):
    with (a.HERE/name).open('w',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def analyze():
    assert a.read(a.WORK/'science-complete.json')['stages']==312
    study.frozen_check()
    behavioral,diagnostics,births,witnesses,stages=[],[],[],[],[]
    cfg=a.read(a.WORK/'configurations.json')
    for seed in a.SEEDS:
        for index in a.HISTORIES:
            name=f's{seed}-c{index}'
            m=a.read(a.WORK/'materials'/f'{name}.json.gz')
            for profile in a.PROFILES:
                folder=a.WORK/'science'/name/profile
                # Recalculate all run endpoints and audit complete states, inputs and time.
                for p in sorted(folder.rglob('result.json')):
                    result=a.read(p);initial=a.read(p.parent/'initial.json.gz');final=a.read(p.parent/'final.json.gz')
                    trace=a.read(p.parent/'trajectory.json.gz');rows=trace['rows']
                    assert len(rows)==result['samples']==round(10*result['seconds'])
                    assert a.digest(initial)==result['origin_hash'] and a.digest(final)==result['final_hash']
                    assert initial['core']['config']==final['core']['config']==cfg[name][profile]
                    assert result['end_us']-result['begin_us']==round(1e6*result['seconds'])
                    assert [r['time_us'] for r in rows]==list(range(result['begin_us'],result['end_us'],100000))
                    assert all(r['body']['phase']==0 for r in rows)
                    assert result['life']!='dead' and final['core']['energy']['unserved_total']==0
                    assert result['region1']==sum(r['region'] for r in rows)/len(rows)
                    assert a.digest(trace['requested'])==result['input_hash']
                    assert len(trace['inputs'])==len(trace['requested'])
                    stages.append({'path':str(p.parent.relative_to(a.WORK)), 'result_hash':a.digest(result),
                                   'input_count':len(trace['requested']), 'passed':True})
                if profile=='legacy1': witnesses.append({'material':name,**a.read(folder/'teaching/historical-witness.json')})
                parent=a.read(folder/'teaching/final.json.gz');newborn=a.read(folder/'newborn.json.gz')
                before=a.digest(parent)
                expected=a.birth(a.StateImage.from_dict(parent['core']),decay_age='preserve').to_dict()
                assert expected==newborn['core'] and a.digest(parent)==before
                pe,ce=edges(parent['core']),edges(newborn['core'])
                observed=a.resolve_kernel(a.kernel(profile)).create(state=a.StateImage.from_dict(parent['core']),backend='reference')
                before_observe=observed.capture_state().digest
                effective=edges(observed.graph())
                assert observed.capture_state().digest==before_observe
                assert effective.keys()==pe.keys(), 'sleeping edges require an explicit additional projection audit'
                effective_error=max((abs(effective[k]-ce.get(k,0)) for k in effective),default=0.)
                assert effective_error<=1e-12
                births.append({'material':name,'profile':profile,'rule':a.read(folder/'birth.json')['metadata']['inheritance_rule'],
                    'parent_nodes':len(parent['core']['nodes']),'child_nodes':len(newborn['core']['nodes']),
                    'parent_edges':len(pe),'child_edges':len(ce),'same_edge_pairs':pe.keys()==ce.keys(),
                    'weight_l1_change':sum(abs(pe.get(k,0)-ce.get(k,0)) for k in pe.keys()|ce.keys()),
                    'weight_max_change':max((abs(pe.get(k,0)-ce.get(k,0)) for k in pe.keys()|ce.keys()),default=0),
                    'effective_parent_to_child_weight_max_error':effective_error,
                    'child_initial_activation':sum(n['activation'] for n in newborn['core']['nodes']),
                    'genuine_birth_exact':True})
                probes={}
                for state in STATES:
                    for motor in ('id','aligned'):
                        results=[a.read(folder/state/motor/f'start{j}/result.json') for j in (0,1)]
                        r1=sum(r['region1'] for r in results)/2
                        behavioral.append({'material':name,'seed':seed,'history':index,'profile':profile,'state':state,
                            'motor':motor,'region1':r1,'target':1-r1 if index==0 else r1,
                            'start0_region1':results[0]['region1'],'start1_region1':results[1]['region1'],
                            'mean_travel':sum(r['travel_distance'] for r in results)/2,
                            'mean_stationary':sum(r['stationary_fraction'] for r in results)/2})
                    for region in (0,1):
                        trace=a.read(folder/state/'probe'/f'region{region}/trajectory.json.gz')
                        rows=trace['rows'];iv,assoc=integrals(rows);probes[state,region]=iv
                        diagnostics.append({'material':name,'profile':profile,'state':state,'region':region,
                            'activation_sum_sampled_area':sum(iv.values()),'associative_sampled_area':assoc,
                            'activation_l1_vs_blank':distance(iv,probes['blank',region]),
                            'id_mean_control':sum(r['controls']['id'] for r in rows)/len(rows),
                            'aligned_mean_control':sum(r['controls']['aligned'] for r in rows)/len(rows),
                            'motor_rule_mean_abs_difference':sum(abs(r['controls']['id']-r['controls']['aligned']) for r in rows)/len(rows)})
                # Identical recorded inputs across initial and offspring curricula,
                # normalized to each stage's own clock; and across all profiles below.
                for phase in ('teaching','offspring-teaching'):
                    trace=a.read(folder/phase/'trajectory.json.gz')
                    offset=a.read(folder/phase/'result.json')['begin_us']
                    normalized=[{'source':r['source'],'time':int(r['stimulus']['time_us'])-offset,
                        'channels':r['stimulus']['channels'],'intensity':r['stimulus']['intensity']} for r in trace['requested']]
                    old=[{'source':r['source'],'time':int(r['stimulus']['time_us']),
                        'channels':r['stimulus']['channels'],'intensity':r['stimulus']['intensity']} for r in m['frames']]
                    key=lambda r:(r['time'],r['source'])
                    assert sorted(normalized,key=key)==sorted(old,key=key)
    assert len(stages)==312
    lookup={(r['material'],r['profile'],r['state'],r['motor']):r for r in behavioral}
    inheritance,expression,prefix=[],[],[]
    for name in {r['material'] for r in behavioral}:
        for profile in a.PROFILES:
            for motor in ('id','aligned'):
                parent=lookup[name,profile,'parent',motor]['target'];child=lookup[name,profile,'newborn',motor]['target']
                inheritance.append({'material':name,'profile':profile,'motor':motor,'parent_target':parent,
                    'newborn_target':child,'qualified_parent':parent>=.75,'retained':parent>=.75 and child>=.75,
                    'decline_at_least_10pp':child-parent<=-.1,
                    'redeveloped_target':lookup[name,profile,'redeveloped',motor]['target']})
            for state in STATES:
                raw=lookup[name,profile,state,'id']['target'];aligned=lookup[name,profile,state,'aligned']['target']
                old=lookup[name,'legacy1',state,'id']['target']
                expression.append({'material':name,'profile':profile,'state':state,'id_target':raw,'aligned_target':aligned,
                    'change_pp':100*(aligned-raw),'substantial':abs(aligned-raw)>=.1,
                    'legacy_gap_recovered':profile!='legacy1' and old-raw>0 and aligned>=.75 and aligned-raw>=(old-raw)/2})
        for state in STATES:
            default=lookup[name,'default63',state,'id']['target'];success=lookup[name,'prefix63',state,'id']['target']
            prefix.append({'material':name,'state':state,'default_target':default,'prefix_target':success,
                'change_pp':100*(success-default),'improved':success-default>=.1 and success>=.75})
    analysis={'schema':'ring-mechanism63/analysis/1','behavior':behavioral,'diagnostics':diagnostics,'birth':births,
        'witnesses':witnesses,'inheritance':sorted(inheritance,key=lambda x:(x['material'],x['profile'],x['motor'])),
        'expression':sorted(expression,key=lambda x:(x['material'],x['profile'],x['state'])),
        'prefix':sorted(prefix,key=lambda x:(x['material'],x['state'])),
        'units':{'peripheral_blocks':2,'historical_materials':4,'stages':312,'not_independent_stages':True}}
    a.save(a.WORK/'analysis-v1/analysis.json',analysis)
    a.save(a.WORK/'analysis-v1/audit.json',{'passed':True,'stages':stages,'all_births_exact':True,
        'all_curricula_exact':True,'frozen_sources_unchanged':True,'all_configs_exact':True})
    a.save(a.HERE/'summary.json',analysis)
    csv_write('behavior.csv',behavioral);csv_write('birth.csv',births);csv_write('diagnostics.csv',diagnostics)
    return analysis

def figures(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import font_manager
    lookup={(r['material'],r['profile'],r['state'],r['motor']):r for r in result['behavior']}
    (a.HERE/'figures').mkdir(exist_ok=True)
    cn_font=next((p for p in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf') if a.Path(p).exists()),None)
    for lang in ('zh','en'):
        plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
        if lang=='zh' and cn_font: plt.rcParams['font.family']=font_manager.FontProperties(fname=cn_font).get_name()
        else: plt.rcParams['font.family']='DejaVu Sans'
        plt.rcParams['axes.unicode_minus']=False
        titles={'legacy1':'/1','default63':'6.3 默认' if lang=='zh' else '6.3 default',
                'prefix63':'6.3 前缀配置' if lang=='zh' else '6.3 prefix configuration'}
        labels=['空白','培养后','出生后','子代再培养'] if lang=='zh' else ['Blank','Developed','Newborn','Redeveloped']
        colors={'legacy1':'#2166ac','default63':'#d95f02','prefix63':'#1b9e77'}
        fig,axes=plt.subplots(2,2,figsize=(11,7.4),sharex=True,sharey=True)
        for j,motor in enumerate(('id','aligned')):
            for i,idx in enumerate(a.HISTORIES):
                ax=axes[i,j];name=f's9293202-c{idx}'
                for profile in a.PROFILES:
                    ys=[100*lookup[name,profile,s,motor]['target'] for s in STATES]
                    ax.plot(range(4),ys,'o-',color=colors[profile],label=titles[profile],lw=1.8,ms=5)
                ax.axhline(75,color='#777777',lw=.8,ls='--');ax.axhline(50,color='#cccccc',lw=.7)
                ax.set_ylim(0,103);ax.set_xticks(range(4),labels,rotation=0 if lang=='zh' else 12)
                title=(('原节点编号规则' if motor=='id' else '按旧通道对应对齐') if lang=='zh' else ('Original node-ID rule' if motor=='id' else 'Aligned historical bindings'))
                ax.set_title(title+('；目标区域' if lang=='zh' else '; target region ')+str(int(idx>0)))
                ax.set_ylabel('目标区域停留比例（%）' if lang=='zh' else 'Target-region occupancy (%)')
        axes[0,0].legend(loc='lower left',frameon=False)
        fig.suptitle('同一旧经历：运动解释、出生与继续培养' if lang=='zh' else 'Matched old experience: motor interpretation, birth and redevelopment',fontsize=15)
        fig.text(.5,.015,'外设 9293202；每点为两个固定起点的平均值；虚线为事先规定的75%标准。' if lang=='zh' else 'Peripheral 9293202; each point averages two fixed starts. Dashed line: prospective 75% criterion.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.95));export(fig,f'01-stages.{lang}');plt.close(fig)
        fig,axes=plt.subplots(1,2,figsize=(11,5),sharey=True)
        for ax,seed in zip(axes,a.SEEDS):
            matrix=[];rowlabels=[]
            for idx in a.HISTORIES:
                name=f's{seed}-c{idx}'
                for p in a.PROFILES:
                    matrix.append([100*lookup[name,p,s,m]['target'] for s in ('parent','newborn') for m in ('id','aligned')])
                    rowlabels.append(f'c{idx} · '+titles[p])
            im=ax.imshow(matrix,vmin=0,vmax=100,cmap='YlGnBu',aspect='auto')
            for ii,row in enumerate(matrix):
                for jj,v in enumerate(row):ax.text(jj,ii,f'{v:.1f}',ha='center',va='center',color='white' if v>65 else 'black',fontsize=10)
            ax.set_yticks(range(6),rowlabels);ax.tick_params(axis='y',labelleft=True)
            ax.set_xticks(range(4),['培养后\n原规则','培养后\n对齐','出生后\n原规则','出生后\n对齐'] if lang=='zh' else ['Parent\nOriginal','Parent\nAligned','Newborn\nOriginal','Newborn\nAligned'])
            ax.set_title(('外设 ' if lang=='zh' else 'Peripheral ')+str(seed))
        fig.suptitle('四份历史材料的目标区域停留比例（%）' if lang=='zh' else 'Target-region occupancy across all four historical materials (%)',fontsize=14)
        fig.tight_layout(rect=(0,.02,1,.92));export(fig,f'02-all-materials.{lang}');plt.close(fig)

def export(fig,name):
    for ext in ('png','svg','pdf'): fig.savefig(a.HERE/'figures'/f'{name}.{ext}',dpi=210,bbox_inches='tight')

if __name__=='__main__':
    analysis=analyze();figures(analysis)
    print('Analysis, full audit, CSV and 12 figure files complete.')
