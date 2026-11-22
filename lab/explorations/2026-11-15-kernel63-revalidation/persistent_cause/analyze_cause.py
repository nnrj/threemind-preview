"""Read-only audit of all 476 stages; preserve the original two-prefix criterion."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_cause as host
e=host.e;s=host.s;read=host.read
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m


def summarize(cases,rows,waits):
    index={r['key']:r for r in rows};assert len(index)==344
    variants=[]
    for name in dict.fromkeys(c['variant'] for c in cases):
        blocks=[];sustained_measured=name not in ('v2-immediate','v63-immediate')
        for block in (0,1):
            prefix=[index[f'{name}/history/s{block}/101/d1/{cue}'] for cue in ('AB','DB')]
            result={'block':block,'prefix_margins':[v['signed_peak'] for v in prefix],
                'prefix_areas':[v['signed_area'] for v in prefix],
                'prefix_passed':all(v['signed_peak']>m.EPS for v in prefix)}
            if sustained_measured:
                activity={arm:index[f'{name}/sustain/s{block}/{arm}']['task_activity'] for arm in host.design.ARMS}
                intact=activity['unchanged']
                result.update(sustained=activity,sustained_passed=intact['first']>m.EPS and intact['minimum']>m.EPS,
                    wait=waits[f'{name}/readout/s{block}/011/paired/d300/wait'])
            blocks.append(result)
        result={'variant':name,'blocks':blocks,'prefix_blocks':sum(b['prefix_passed'] for b in blocks)}
        if sustained_measured:result['sustained_blocks']=sum(b['sustained_passed'] for b in blocks)
        variants.append(result)
    return variants


def analyze(work):
    host.check(work);assert read(work/'summary.json')['stages']==476
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    cases=read(work/'cases.json');records={};rows=[];waits={};baseline=[];nstate=0;ninput=0
    prior=work.parent/'memory-timescales-63-rerun-v1'
    norm=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
    for i,c in enumerate(cases):
        folder=work/'cases'/c['key'];r=read(folder/'result.json')
        assert r['status']=='complete' and r['kernel']=='threemind.continuous-memory/'+c['version']
        assert r['begin_us']==c['begin_us'] and r['end_us']==c['end_us'] and r['life']=='active'
        assert not r['calibration'] and r['mode']=='observed'
        images={name:e.base.image(folder/(name+'.tmind')) for name in ('initial','intervened','final')}
        for name,im in images.items():
            assert im.digest==r[name+'_sha256'] and im.to_dict()['dynamics']==r['kernel'];nstate+=1
        if c['parent']:
            assert records[c['parent']]['final_sha256']==r['parent_sha256']==r['initial_sha256']
            assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(work/'cases'/c['parent']/'observer.json.xz')
        before,changed,final=[images[n].to_dict() for n in ('initial','intervened','final')]
        assert changed['config']==before['config']|c['patch']|c['cause_patch']
        assert final['config']==changed['config']
        assert int(before['time_us'])==int(changed['time_us'])==c['begin_us'] and int(final['time_us'])==c['end_us']
        intervention=read(folder/'intervention.json')
        assert intervention['advanced_us']==0 and intervention['changes']==e.support.x.differences(before,changed)
        inputs=e.unpacked(folder/'inputs.json.xz');assert inputs==e.material_frames(c,work/'materials')
        delivered=e.unpacked(folder/'delivered.json.xz');scheduled=e.unpacked(folder/'scheduled.json.xz')
        assert len(inputs)==len(delivered)==len(scheduled)==r['inputs'];ninput+=len(inputs)
        by_event={}
        for a,b in zip(inputs,scheduled):
            assert a['enqueue_us']==b['enqueue_us'] and a['source']==b['receipt']['source']
            assert int(a['stimulus']['time_us'])==int(b['receipt']['scheduled_time_us'])
            by_event[b['receipt']['core_event_id']]=b['enqueue_us']
        assert len(by_event)==len(inputs)
        assert Counter(norm({k:v[k] for k in ('stimulus','source','enqueue_us')}) for v in inputs)==Counter(
            norm({'stimulus':v['stimulus'],'source':v['source'],'enqueue_us':by_event[v['core_event_id']]}) for v in delivered)
        assert all(int(v['core_sequence'])>0 and not v.get('labels') and
            v['stimulus']['time_us']==v['scheduled_time_us']==v['delivered_time_us'] for v in delivered)
        if c['kind']=='readout_wait':assert not any(v['source']=='manual-probe' for v in inputs)
        with zipfile.ZipFile(folder/'milestones.zip') as archive:
            assert set(archive.namelist())=={name+'.tmind' for name in r['snapshots']}
            for name,digest in r['snapshots'].items():
                im=e.base.ArtifactCodec.decode(archive.read(name+'.tmind'))
                assert im.digest==digest and im.to_dict()['dynamics']==r['kernel'];nstate+=1
        assert e.unpacked(folder/'observer.json.xz')['input_bus']['pending']=={}
        points=e.unpacked(folder/'trajectory.json.xz')['points']
        if c['kind']=='probe':rows.append(m.process(c,points))
        if c['kind']=='readout_wait':
            values=[(p['time_us']-c['begin_us'],max((n['activation'] for n in p['nodes']),default=0.)) for p in points]
            waits[c['key']]={'last_positive_us':max((t for t,v in values if v>0),default=None),'end':values[-1][1],
                'checkpoints':{str(seconds):next((v for t,v in values if t==seconds*1000000),None) for seconds in (1,30,60,300)}}
        if c['variant']=='v63':
            reference=read(prior/'cases'/c['material_key']/'result.json')
            assert r['final_sha256']==reference['final_sha256'],('new 6.3 reference differs',c['key'])
            baseline.append({'key':c['key'],'digest':r['final_sha256']})
        records[c['key']]=r
        if (i+1)%32==0:print('audited',i+1,'/476',flush=True)
    variants=summarize(cases,rows,waits);comparison=host.design.compare_targets(variants)
    index={r['key']:r for r in rows};old_check=[]
    for block in (0,1):
        for cue in ('AB','DB'):
            key=f'history/s{block}/101/d1/{cue}'
            old=read(e.materials.OLD/'cases'/key/'result.json')['extra']['post_cue'];row=index['v1/'+key]
            value=old[row['target']]['peak']-old[row['other']]['peak']
            old_check.append({'key':key,'historical':value,'replayed':row['signed_peak'],'absolute_error':abs(value-row['signed_peak'])})
    assert all(v['absolute_error']<1e-9 for v in old_check),'unchanged historical /1 prefix witness differs'
    assert len(baseline)==20 and nstate==2248 and ninput==44652 and len(waits)==48
    costs=read(work/'resource-summary.json')
    maximum=max(r['arithmetic_error'] for r in rows)
    result={'variants':variants,'process':rows,'old_prefix_replay':old_check,'source_blocks':2,'stages':476,
        'historical_comparison':comparison,'scientific_stop':comparison['scientific_stop'],
        'maximum_arithmetic_error':maximum}
    s.base.original(work/'analysis.json',result)
    s.base.original(work/'audit.json',{'passed':True,'scientific_stop':comparison['scientific_stop'],
        'stages':476,'complete_states':nstate,'inputs':ninput,'waits_without_task_prompts':48,
        'exact_63_references':baseline,'historical_prefix_replay':old_check,'maximum_arithmetic_error':maximum,
        'apparatus':read(work/'apparatus.json'),'resources':costs})
    print(json.dumps({'conditions':[(v['variant'],v.get('sustained_blocks'),v['prefix_blocks']) for v in variants],
        'new_adverse_difference':comparison['scientific_stop']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();analyze(a.work)
