"""Compact process/results analysis; no kernel or original evidence writes."""
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/body-exploration-20261007'


def records(key):
    with gzip.open(WORK/'cases'/key/'process.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:yield json.loads(line)


def physical_series(key):
    """Measured process only; no target interpretation is sent to the model."""
    from types import SimpleNamespace
    from lab.tools.eye_hand_world import teacher_eye_angle
    rows=[]
    for record in records(key):
        for r in record['process']:
            ob=r['observation'];world=SimpleNamespace(origin=np.array(ob['camera']['origin_m']))
            angles=[teacher_eye_angle(world,xy) for xy in ob['positions']]
            error=float(min(np.linalg.norm(np.array(ob['eye_angle_rad'])-a) for a in angles))
            rows.append({'time_s':ob['time_s'],'eye_nearest_toy_error_rad':error,
                'eye_speed_rad_s':float(np.linalg.norm(ob['eye_velocity_rad_s'])),
                'contacts':ob['toy_contacts'],'eye':ob['eye_angle_rad'],
                'hand':[ob['pointer']['x'],ob['pointer']['y']],
                'command':r['eye_action']+r['hand_action']+r['mouth_action'],
                'variation':r['developmental_motor']['motor_variation']})
    return rows


def main():
    results={p.parent.name:json.loads(p.read_text(encoding='utf-8')) for p in (WORK/'cases').glob('*/result.json')}
    out={'schema':'threemind.body-exploration-results/1','cases':results,'paired':{},'caregiver':{},'actuators':{},'teacher_fit':{},
         'interpretation_correction':{'date':'2026-10-07','scope':'segmented pipeline; NOT continuous Core plus Transformer development',
             'withdrawn':'preschool lacks benefit for the continuously developing whole system',
             'evidence_preserved':True,'document':'continuity-correction.en.md'}}
    for key,value in results.items():
        if not key.startswith('C-'):continue
        validation=WORK/'cases'/('V-'+key[2:])/'features.npz'
        with np.load(validation) as data:y=data['y']
        out['teacher_fit'][key]={'mean_absolute_teacher_command':np.abs(y).mean(axis=0).tolist(),
            'constant_zero_validation_mse':float(np.mean(y*y)),
            'learned_validation_mse':value['fit']['validation_mse'],
            'scope':'posthoc descriptive comparison; not a new model selection or success criterion'}
    # This diagnostic summarizes actual commands, not a new success criterion.
    for key in results:
        if not (key.startswith('D-') or key.startswith('P-test-')):continue
        commands=[];by_mode={};corrective=[]
        for record in records(key):
            values=np.array([r['eye_action']+r['hand_action'] for r in record['process']])
            commands.extend(values);by_mode.setdefault(record['task']['mode'],[]).extend(values)
            for row,et,ht in zip(record['process'],record['scoring_only_eye_targets'],record['scoring_only_hand_targets'],strict=True):
                ob=row['observation'];hand=ob['pointer']
                # Post-hoc diagnostic only. Scoring targets never enter normal
                # Core input or either learned reader in this experiment.
                eye=np.clip(16*(np.asarray(et)-ob['eye_angle_rad'])-2*np.asarray(ob['eye_velocity_rad_s']),-1,1)
                force=np.clip(3*(np.asarray(ht)-[hand['x'],hand['y']])-.9*np.array([hand['vx'],hand['vy']]),-1,1)
                corrective.append(np.r_[eye,force])
        x=np.array(commands)
        out['actuators'][key]={'mean':x.mean(axis=0).tolist(),'standard_deviation':x.std(axis=0).tolist(),
            'mean_absolute':np.abs(x).mean(axis=0).tolist(),'saturated_fraction':(np.abs(x)>.95).mean(axis=0).tolist(),
            'by_mode_mean':{k:np.mean(v,axis=0).tolist() for k,v in by_mode.items()},
            'posthoc_corrective_force_mae':np.abs(x-np.array(corrective)).mean(axis=0).tolist(),
            'posthoc_mean_required_correction':np.abs(corrective).mean(axis=0).tolist()}
    comparisons=[]
    for source in (0,1):
        base=f'D-gain01-{source}-explore-read-explore-normal'
        for other in (f'D-gain01-{source}-quiet-read-explore-normal',
                      f'D-gain01-{source}-explore-read-explore-silence',
                      f'D-gain01-{source}-explore-read-explore-rescue',
                      f'D-gain01-{source}-explore-read-explore-empty'):
            if base in results and other in results:comparisons.append((base,other))
        quiet=f'D-gain01-{source}-quiet-read-quiet-normal'
        swapped=f'D-gain01-{source}-explore-read-quiet-normal'
        if quiet in results and swapped in results:comparisons.append((quiet,swapped))
        pose=f'P-test-{source}-explore'
        for suffix in ('silence','rescue','empty'):
            other=pose+'-'+suffix
            if pose in results and other in results:comparisons.append((pose,other))
        zero=f'D-gain01-{source}-explore-read-explore-empty'
        if pose in results and zero in results:
            out.setdefault('shared_controls',{})[pose]={'zero_command':zero,'independent_new_sample':False}
    for left,right in comparisons:
        changes=[]
        for a,b in zip(records(left),records(right),strict=True):
            aa=np.array([r['eye_action']+r['hand_action'] for r in a['process']]);bb=np.array([r['eye_action']+r['hand_action'] for r in b['process']])
            changes.append({'index':a['task']['index'],'mode':a['task']['mode'],
                'max_command_difference':float(np.max(np.abs(aa-bb))),
                'eye_endpoint_difference':float(np.linalg.norm(np.array(a['result']['eye_final'])-b['result']['eye_final'])),
                'hand_endpoint_difference':float(np.linalg.norm(np.array(a['result']['hand_final'])-b['result']['hand_final']))})
        out['paired'][right]={'reference':left,'command_changed_trials':sum(x['max_command_difference']>1e-7 for x in changes),
            'endpoint_changed_trials':sum(max(x['eye_endpoint_difference'],x['hand_endpoint_difference'])>1e-7 for x in changes),'trials':changes}
    caregiver_series={}
    for source in (0,1):
        guide=f'A-gain01-{source}-guided'
        if guide not in results:continue
        series=physical_series(guide);caregiver_series[source]=series
        bins=[]
        for start in range(0,180,10):
            chunk=[r for r in series if start<=r['time_s']<start+10]
            if not chunk:continue
            bins.append({'start_s':start,'looking_fraction':float(np.mean([r['eye_nearest_toy_error_rad']<=.075 for r in chunk])),
                'contacts_end':chunk[-1]['contacts']})
        data={'ten_second_process':bins,'probes':{}}
        for version in ('W','W2'):
            normal=f'{version}-gain01-{source}-guided-normal'
            if normal not in results:continue
            baseline=physical_series(normal)
            for other in (f'{version}-gain01-{source}-explore-normal',f'{version}-gain01-{source}-guided-cut'):
                if other not in results:continue
                rows=physical_series(other)
                pairs=list(zip(baseline,rows,strict=True))
                data['probes'][other]={
                    'reference':normal,
                    'preschool_wiring_preserved':version=='W2',
                    'interpretation':'familiar-body comparison' if version=='W2' else 'original probe accidentally changed wiring; retained with correction',
                    'max_command_difference':float(max(np.max(np.abs(np.array(a['command'])-b['command'])) for a,b in pairs)),
                    'max_variation_difference':float(max(np.max(np.abs(np.array(a['variation'])-b['variation'])) for a,b in pairs)),
                    'eye_endpoint_difference_rad':float(np.linalg.norm(np.array(baseline[-1]['eye'])-rows[-1]['eye'])),
                    'hand_endpoint_difference_m':float(np.linalg.norm(np.array(baseline[-1]['hand'])-rows[-1]['hand']))}
        out['caregiver'][str(source)]=data
    with (HERE/'results.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    # Publication-sized static figure. All registered conditions are shown.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='DejaVu Sans'
    fig,axs=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    colors=['#167963','#bc8739','#738aaf']
    for source in (0,1):
        for j,group in enumerate(('explore','quiet','yoked')):
            k=f'D-gain01-{source}-{group}-read-{group}-normal'
            if k not in results:continue
            r=results[k];x=source*4+j
            axs[0,0].bar(x,r['eye_enter_and_finish'],color=colors[j]);axs[0,1].bar(x,r['hand_enter_and_finish'],color=colors[j])
            p=f'A-gain01-{source}-{group}'
            if p in results:
                a=results[p];axs[1,0].bar(x,a['contacts'],color=colors[j]);axs[1,1].bar(x,a['eye_boundary_fraction']*100,color=colors[j])
    for ax,title in zip(axs.ravel(),['Eye: entered and finished aligned / 12','Hand: entered and finished arrived / 12','Preschool toy contacts','Preschool eye at physical boundary (%)']):
        ax.set_title(title);ax.set_xticks([0,1,2,4,5,6],['Explore\nS0','Quiet\nS0','Replay\nS0','Explore\nS1','Quiet\nS1','Replay\nS1']);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axs[0,0].set_ylim(0,12);axs[0,1].set_ylim(0,12)
    fig.suptitle('E61: segmented-controller pipeline\nNot a test of continuous Core + Transformer development',fontsize=13)
    fig.savefig(WORK/'body-exploration-results.png',dpi=150);plt.close(fig)
    if caregiver_series:
        fig,axs=plt.subplots(len(caregiver_series),2,figsize=(11,3*len(caregiver_series)),squeeze=False,layout='constrained')
        for i,(source,series) in enumerate(caregiver_series.items()):
            times=[r['time_s'] for r in series]
            axs[i,0].plot(times,[r['eye_nearest_toy_error_rad'] for r in series],color='#167963',linewidth=.7)
            axs[i,0].axhline(.075,color='#bc8739',linestyle=':');axs[i,0].set_ylabel('Nearest toy error (rad)')
            axs[i,1].plot(times,[r['contacts'] for r in series],color='#167963');axs[i,1].set_ylabel('Cumulative contacts')
            for ax in axs[i]:
                ax.axvline(120,color='#8c557b',linestyle='--');ax.set_xlabel('Simulation seconds');ax.set_title(f'Source {source}: caregiver withdrawn at 120 s');ax.grid(alpha=.2)
        fig.savefig(WORK/'caregiver-process.png',dpi=150);plt.close(fig)
    print(json.dumps({'completed_cases':len(results),'paired':{k:v['command_changed_trials'] for k,v in out['paired'].items()}}))


if __name__=='__main__':main()
