"""Read-only complete-state, input and response audit of R63i."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(HERE),str(HERE.parent),str(ROOT/'src')]
import spec as design
import measurement as measure
import support as s
from allocation import disk_allocation
from threemind_runtime import ArtifactCodec

def read(p):return measure.read(p)

def change(base,arm):
    rows=[]
    for a,b in zip(base['blocks'],arm['blocks']):
        assert a['seed']==b['seed']
        preserved=a['joint_correct']>=3 and b['joint_correct']>=3
        rows.append({'seed':a['seed'],'taught_to_reverse':preserved and a['full_correct']>=3 and b['full_opposite']>=3,
                     'reverse_to_taught':preserved and a['full_opposite']>=3 and b['full_correct']>=3})
    forward=sum(x['taught_to_reverse'] for x in rows);back=sum(x['reverse_to_taught'] for x in rows)
    return {'reference':base['variant'],'reference_arm':base['arm'],'condition':arm['variant'],'condition_arm':arm['arm'],
            'blocks':rows,'taught_to_reverse_blocks':forward,'reverse_to_taught_blocks':back,
            'selective_direction_change':max(forward,back)>=3}

def anatomy(points):
    seen={};lost=0;born=0;min_weight=None
    for p in points:
        g=p['graph'];nodes={n['id']:n['channel'] for n in g['nodes']}
        now={(nodes[e['source']],nodes[e['target']],str(e.get('birth_us'))):e['weight'] for e in g['edges']}
        lost+=len(seen.keys()-now.keys());born+=len(now.keys()-seen.keys())
        if now:min_weight=min(min_weight if min_weight is not None else 1.,min(now.values()))
        seen=now
    return {'observed_disappearances':lost,'observed_births':born,'minimum_observed_weight':min_weight,
            'maximum_nodes':max(len(p['graph']['nodes']) for p in points),
            'maximum_edges':max(len(p['graph']['edges']) for p in points)}

def analyze(work):
    assert not (work/'in-flight.json').exists()
    summary=read(work/'summary.json');frozen=read(work/'frozen.json')
    for rel,item in frozen['historical_evidence'].items():assert s.sha(work/rel)==item['sha256']
    assert s.sha(work/'subjects.json')==read(work/'calibration.json')['subjects_sha256']
    subjects=read(work/'subjects.json');states=0;stage_count=0;directions=[];structures=[];deliveries=0;patches=0
    for subj in subjects:
        folder=work/'subjects'/subj['key']
        if not folder.exists():continue
        for stage in design.stages(subj):
            d=folder/stage['name']
            r=read(d/'result.json');inputs=read(d/'input.json')
            assert r['status']=='complete' and r['life']=='active' and inputs['subject']==subj and inputs['stage']==stage
            assert r['kernel']==subj['kernel'] and r['end_us']==stage['end_us']
            images=[]
            for filename,key,t in [('initial.tmind','initial_sha256',stage['begin_us']),('final.tmind','final_sha256',stage['end_us'])]:
                im=ArtifactCodec.decode((d/filename).read_bytes());doc=im.to_dict()
                assert im.digest==r[key] and doc['dynamics']==subj['kernel'] and int(doc['time_us'])==t
                assert doc['config']['seed']==subj['seed'];images.append(doc);states+=1
            if stage['parent']:
                parent=read(folder/stage['parent']/'result.json')
                assert r['initial_sha256']==r['parent_sha256']==parent['final_sha256']
            if stage.get('test_patch'):
                patch=read(d/'intervention.json');im=ArtifactCodec.decode((d/'intervened.tmind').read_bytes())
                assert im.digest==patch['after'] and patch['before']==r['initial_sha256']
                assert int(im.to_dict()['time_us'])==stage['begin_us']
                assert all(im.to_dict()['config'][k]==v for k,v in stage['test_patch'].items());patches+=1
            received=read(d/'delivered.json.gz')
            expected=design.inputs(work/'historical',subj,stage,inputs['mappings'])
            assert inputs['frames']==expected and len(received)==len(expected)
            def stim_key(v):return (int(v['time_us']),tuple(tuple(x) for x in v['channels']),v['intensity'])
            assert sorted(stim_key(x['stimulus']) for x in received)==sorted(stim_key(x['stimulus']) for x in expected)
            assert all(x['scheduled_time_us']==x['delivered_time_us'] for x in received)
            deliveries+=len(received)
            points=read(d/'trajectory.json.gz')['points']
            assert [x['time_us'] for x in points]==list(range(stage['begin_us'],stage['end_us']+1,100000))
            structures.append({'subject':subj['key'],'variant':subj['variant'],'stage':stage['name'],**anatomy(points)})
            stage_count+=1
        arms=['intact']+(['test-no-inhibition','test-no-fast'] if subj['variant'] in ('v2','v63') and subj['mode'] in ('full','no_imu') else [])
        for arm in arms:directions+=measure.scores(work,subj,arm)
        print(subj['key'],stage_count,flush=True)
    assert stage_count==summary['stages'] and states==2*stage_count
    variants=[v[0] for v in design.VARIANTS if any(x['variant']==v[0] for x in directions)]
    blocks=[measure.block_summary(directions,v) for v in variants]
    for v in ('v2','v63'):
        for arm in ('test-no-inhibition','test-no-fast'):
            if any(x['variant']==v and x['arm']==arm for x in directions):blocks.append(measure.block_summary(directions,v,arm))
    lookup={(b['variant'],b['arm']):b for b in blocks};comparisons=[]
    for b in blocks:
        v=b['variant'];arm=b['arm']
        if arm!='intact':reference=v
        elif v in ('v2','v31','v51','v53','v63'):continue
        elif v=='v31-no-fatigue':reference='v31'
        else:reference='v2' if v.startswith('v2-') else 'v63'
        if (reference,'intact') in lookup:comparisons.append(change(lookup[reference,'intact'],b))
    group_counts=[]
    for variant in variants:
        for mode in design.MODES:
            rows=[r for r in directions if r['variant']==variant and r['mode']==mode and r['arm']=='intact']
            if rows:group_counts.append({'variant':variant,'mode':mode,'n':len(rows),
                'post_input':dict(Counter(r['windows']['post_input']['direction'] for r in rows)),
                'input':dict(Counter(r['windows']['input']['direction'] for r in rows)),
                'common_blank_window':dict(Counter(r['windows']['common_blank_window']['direction'] for r in rows))})
    independent_error=max(x['maximum_Decimal_error'] for r in directions for x in r['windows'].values())
    assert independent_error<1e-10
    no_delete=lookup.get(('v2-no-delete','intact'))
    necessary_rejected=bool(no_delete and no_delete['old_relation_blocks']>=3 and lookup['v2','intact']['old_relation_blocks']>=3)
    old_lost=sum(x['observed_disappearances'] for x in structures if x['variant']=='v2')
    scientific_stop=bool(summary.get('scientific_stop_reason'))
    files=[p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result={'schema':'threemind.r63i-analysis/1','independent_material_blocks':4,'formal_stages':stage_count,
        'responses':directions,'groups':group_counts,'block_results':blocks,'causal_comparisons':comparisons,
        'structure':structures,'historical_deletion_necessity_rejected':necessary_rejected,
        'historical_observed_disappearances':old_lost,'calibration':read(work/'calibration.json'),
        'historical_weight_lower_bound':read(work/'plan-check.json')['historical_deletion_bound'],
        'baseline':read(work/'baseline-check.json'),'scientific_stop':scientific_stop,'summary':summary,
        'resources':read(work/'resource-summary.json'),
        'storage':{'logical_bytes':sum(p.stat().st_size for p in files),
                   'allocated_bytes':sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    s.base.original(work/'analysis.json',result)
    s.base.original(work/'audit.json',{'passed':True,'complete_initial_final_states':states,'additional_intervention_states':patches,
        'formal_stages':stage_count,'delivered_inputs_verified':deliveries,'integral_precision':45,
        'maximum_integral_error':independent_error,'Core_engines_loaded':0,'scientific_stop':scientific_stop})
    print(json.dumps({'stages':stage_count,'groups':group_counts,'blocks':blocks,
        'deletion_necessity_rejected':necessary_rejected,'scientific_stop':scientific_stop}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);analyze(p.parse_args().work.resolve())
