"""Audit v2: enforce the documented empty mapping for the input bus.

The frozen v1 expected an empty list and failed before scientific scoring.
Only that schema assertion and the qualified entry point differ; v1 is kept.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_timescales as r
from threemind_kernels.local61 import Local61Config
e=r.e;m=r.m;read=r.read


def analyze(work):
    r.check(work)
    assert not (work/'in-flight.json').exists() and read(work/'summary.json')['stages']==592
    cases=read(work/'cases.json');counts=Counter();results={};rows=[];structure=[];observer_checks=[]
    def inspect(image,expected=None):
        value=image.to_dict()
        assert value['dynamics']==r.mat.KERNEL and value['life'] in ('waiting','active')
        assert all(n['id']==n['channel'] for n in value['nodes'])
        config=value['config']
        if expected is not None:assert config==expected
        assert config['signal_threshold']==.0004 and config['prune_weight']==.008
        assert config['decay_curve']=='inverse-logarithmic' and not config['retention_growth_enabled']
        counts['states']+=1
        return value
    for number,c in enumerate(cases):
        folder=work/'cases'/c['key'];result=read(folder/'result.json')
        assert result['key']==c['key'] and result['status']=='complete' and result['life']=='active'
        assert not result['calibration'] and result['mode']=='observed' and result['kernel']==r.mat.KERNEL
        initial=e.base.image(folder/'initial.tmind');changed=e.base.image(folder/'intervened.tmind');final=e.base.image(folder/'final.tmind')
        if c['parent']:
            parent=e.base.image(work/'cases'/c['parent']/'final.tmind')
            assert initial.digest==parent.digest==result['parent_sha256']
            previous=e.unpacked(work/'cases'/c['parent']/'observer.json.xz')
            assert e.unpacked(folder/'initial-observer.json.xz')==previous
            initial_cfg=parent.to_dict()['config']
        else:
            initial_cfg=Local61Config(seed=r.mat.SEED,**c['initial_config']).to_dict()
            assert result['parent_sha256'] is None
        a=inspect(initial,initial_cfg);b=inspect(changed,initial_cfg|c['patch']);z=inspect(final,initial_cfg|c['patch'])
        assert int(a['time_us'])==int(b['time_us'])==c['begin_us'] and int(z['time_us'])==c['end_us']
        assert initial.digest==result['initial_sha256'] and changed.digest==result['intervened_sha256'] and final.digest==result['final_sha256']
        receipt=read(folder/'intervention.json')
        assert receipt['advanced_us']==0 and receipt['patch']==c['patch']
        assert receipt['before']==initial.digest and receipt['after']==changed.digest
        assert receipt['changes']==e.support.x.differences(a,b)
        expected=e.material_frames(c,work/'materials')
        assert e.unpacked(folder/'inputs.json.xz')==expected
        delivered=e.unpacked(folder/'delivered.json.xz');scheduled=e.unpacked(folder/'scheduled.json.xz')
        assert len(expected)==len(delivered)==len(scheduled)==result['inputs']
        by_event={}
        for frame,sent in zip(expected,scheduled):
            assert frame['enqueue_us']==sent['enqueue_us']
            assert frame['source']==sent['receipt']['source']
            assert int(frame['stimulus']['time_us'])==int(sent['receipt']['scheduled_time_us'])
            by_event[sent['receipt']['core_event_id']]=sent['enqueue_us']
        norm=lambda item:json.dumps(item,sort_keys=True,separators=(',',':'))
        assert Counter(norm({k:v[k] for k in ('stimulus','source','enqueue_us')}) for v in expected)==Counter(
            norm({'stimulus':v['stimulus'],'source':v['source'],'enqueue_us':by_event[v['core_event_id']]}) for v in delivered)
        assert all(not v.get('labels') and v['stimulus']['time_us']==v['scheduled_time_us']==v['delivered_time_us'] for v in delivered)
        counts['inputs']+=len(expected)
        projections=e.unpacked(folder/'projections.json.xz')
        with zipfile.ZipFile(folder/'milestones.zip') as archive:
            expected_names={'end'}|({'before_probe'}|set(map(str,c['milestones'])) if c['kind']=='probe' else set())
            assert set(result['snapshots'])==expected_names==set(projections)
            assert set(archive.namelist())=={k+'.tmind' for k in expected_names}
            for name in sorted(expected_names):
                image=e.base.ArtifactCodec.decode(archive.read(name+'.tmind'))
                doc=inspect(image,initial_cfg|c['patch'])
                assert image.digest==result['snapshots'][name]
                assert int(doc['time_us'])==projections[name]['time_us']
                if name=='end':assert image.digest==final.digest
        whole=e.unpacked(folder/'observer.json.xz')
        assert whole['input_bus']['schema']=='threemind.input-bus/1'
        assert isinstance(whole['input_bus']['pending'],dict) and whole['input_bus']['pending']=={}
        trajectory=e.unpacked(folder/'trajectory.json.xz')
        if c['kind']=='probe':
            measured=m.process(c,trajectory['points'])
            manual={v['receipt']['envelope_id'] for v in scheduled if v['receipt']['source']=='manual-probe'}
            windows=[v['payload'] for v in trajectory['events'] if v['kind']=='temporal_readout' and v['payload']['envelope_id'] in manual]
            window=windows[-1] if windows else None
            assert len(manual)==(0 if c['cue']=='none' else 1)
            assert result['classification']==(window['classification'] if window else 'no_window')
            assert result['reason']==(window['reason'] if window else 'no_window')
            values={v['node_id']:v['last_activation'] for v in window['nodes']} if window else {}
            target=r.mat.TOKENS[measured['target']];other=r.mat.TOKENS[measured['other']]
            measured.update(classification=result['classification'],reason=result['reason'],
                qualified=result['classification']=='converged',
                qualified_target_margin=values.get(target,0.)-values.get(other,0.) if result['classification']=='converged' else None,
                old_signed_peak=c['old_post_cue'][measured['target']]['peak']-c['old_post_cue'][measured['other']]['peak'])
            rows.append(measured)
            if c['key'].startswith('retention/'):
                graph=projections['before_probe']['graph']
                edges=graph['edges'];source=r.mat.TOKENS[c['cue']]
                weights={v['target']:v['weight'] for v in edges if v['source']==source}
                task={n['channel']:n['activation'] for n in projections['before_probe']['nodes'] if n['channel'] in r.mat.TOKENS.values()}
                structure.append({'key':c['key'],'matched_weight':weights.get(target,0.),'other_weight':weights.get(other,0.),
                    'weight_margin':weights.get(target,0.)-weights.get(other,0.),'pre_cue_task_activation':task})
            if c['key'].startswith('diagnostic/'):
                _,bits,cue=c['key'].split('/')
                other_folder=work/'cases'/f'short/s0/{bits}/g1/{cue}'
                assert final.digest==read(other_folder/'result.json')['final_sha256']
                # Observer carrier identities differ between diagnostic copies; Core and task process must agree.
                assert trajectory['points']==e.unpacked(other_folder/'trajectory.json.xz')['points']
                observer_checks.append({'key':c['key'],'final_core_exact':True,'trajectory_exact':True})
        else:assert not trajectory['points']
        results[c['key']]=result;counts['stages']+=1
        if (number+1)%64==0:print('audited',number+1,flush=True)
    assert counts['stages']==592 and counts['inputs']==41248 and len(rows)==510 and len(structure)==192 and len(observer_checks)==4
    decisions=m.decide(rows)
    residual=[]
    index={v['key']:v for v in rows}
    for c in cases:
        if c['key'].startswith('retention/') and c.get('delay_s')==1:
            row=index[c['key']];key=c['key'].split('/d1/')[0].replace('retention/','residual/',1)
            control=index[key]['measures'];control_margin=control[row['target']]['activation']['peak']-control[row['other']]['activation']['peak']
            residual.append({'key':c['key'],'control':key,'signed_peak':row['signed_peak'],'uncued_signed_peak':control_margin,
                             'adjusted':row['signed_peak']-control_margin})
    assert len(residual)==64
    analysis={'kernel':r.mat.KERNEL,'material_blocks':2,'counts':dict(counts),'process':rows,'decisions':decisions,
        'structure':structure,'residual_controls':residual,'observer_checks':observer_checks,
        'classifications':dict(Counter(v['classification'] for v in rows)),
        'maximum_arithmetic_error':max(v['arithmetic_error'] for v in rows)}
    r.s.base.original(work/'analysis.json',analysis)
    audit={'passed':True,'read_only':True,'created_engines':0,'counts':dict(counts),'scientific_stop':decisions['scientific_stop'],
        'maximum_arithmetic_error':analysis['maximum_arithmetic_error'],'observer_checks':len(observer_checks)}
    r.s.base.original(work/'audit.json',audit)
    print(json.dumps(audit),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    import comparable_budget_v3 as runner
    runner.check(a.work.resolve());read=runner.read
    analyze(a.work.resolve())
