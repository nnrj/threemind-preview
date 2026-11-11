"""Paired process comparisons, separate from terminal performance and selection."""
import gzip
import json
import numpy as np
from experiment import WORK
from analyze import cases
from lab.tools.ocean import difference
from lab.tools.ocean_cli import read_json


def read(case):
    with gzip.open(WORK/case['path']/'trajectory.json.gz','rt',encoding='utf-8') as f:return json.load(f)


def compare(a,b,side):
    # Match recorded clock samples, never compare different living-time averages.
    results={}
    for lo,hi in ((0,.5),(.5,2),(2,6),(6,20),(0,20)):
        pairs=[(x,y) for x,y in zip(a,b) if lo<=x['t']<hi and x['t']==y['t'] and x['physical'] and y['physical']]
        results[f'{lo}-{hi}']={'living_pairs':len(pairs),
            'action_mae':float(np.mean([np.mean(np.abs(np.asarray(x['action'])-y['action'])) for x,y in pairs])) if pairs else None,
            'mean_path_gap_m':float(np.mean([np.linalg.norm(difference(x['position'],y['position'],side)) for x,y in pairs])) if pairs else None}
    return results


def activity_difference(a,b,targets):
    def load(case):
        with gzip.open(WORK/case['path']/'activity.json.gz','rt',encoding='utf-8') as f:return json.load(f)
    sums=[];clean_samples=0
    for left,right in zip(load(a),load(b)):
        # The recording starts at the fork. Earlier samples lack a full second
        # of input history and cannot establish absence of recent direct input.
        if left['t']!=right['t'] or left['t']<1:continue
        by_id={n['id']:n for n in right['nodes']}
        recent=set(left['recent_channels'])|set(right['recent_channels'])
        pairs=[(n,by_id[n['id']]) for n in left['nodes'] if n['id'] in targets and n['id'] in by_id
               and n['channel'] not in recent and n['activation']>.004]
        if pairs:
            clean_samples+=len(pairs)
            sums.append(sum(x['activation']-y['activation'] for x,y in pairs))
    return {'unprompted_node_samples':clean_samples,'mean_activation_reduction':float(np.mean(sums)) if sums else None}


def run():
    rows=cases(recompute_contacts=False);lookup={(r['donor'],r['assay']['task'],r['side'],r['assay']['operation']):r for r in rows}
    result={'comparison':'same recorded times; only pairs with both physical; no frame-as-independent inference',
            'side_changes':[],'interventions':[],'graft_action_similarity':[]}
    for r in rows:
        if r['assay']['operation']!='intact' or r['assay']['task']=='transfer':continue
        a=read(r);donor,task,side=r['donor'],r['assay']['task'],r['side']
        for op in ('replay','target','matched','all'):
            other=lookup.get((donor,task,side,op))
            if other:
                row={'donor':donor,'task':task,'side':side,'operation':op,
                    'windows':compare(a,read(other),.8),'source':r['path'],'other':other['path']}
                if op in ('target','matched'):
                    plan=read_json(WORK/'plans'/f'{donor}-{task}.json')
                    row['target_activity']=activity_difference(r,other,set(plan['targets']))
                result['interventions'].append(row)
        if side==0:
            other=lookup.get((donor,task,1,'intact'))
            if other:result['side_changes'].append({'donor':donor,'task':task,'windows':compare(a,read(other),.8)})
    for r in rows:
        if r['assay']['operation']!='experienced':continue
        donor,task,side=r['donor'],r['assay']['task'],r['side']
        reference=read(r);distances={}
        for op in ('blank','graft','graft-matched'):
            other=lookup.get((donor,task,side,op))
            if other:distances[op]=compare(reference,read(other),.8)['0-20']
        if len(distances)==3:result['graft_action_similarity'].append({'donor':donor,'task':task,'side':side,'distances':distances})
    target=WORK/'process-findings.json';temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8');temp.replace(target)
    return result


if __name__=='__main__':
    result=run()
    for task in ('food','hunt','escape'):
        rows=[r['windows']['0-20']['action_mae'] for r in result['side_changes'] if r['task']==task]
        print(json.dumps({'task':task,'paired_donors':len(rows),'side_switch_action_mae':rows}))
