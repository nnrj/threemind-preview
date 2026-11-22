"""Read-only verification and independent arithmetic for R51t10."""
import argparse
from copy import deepcopy
import gzip
import json
import lzma
from pathlib import Path
import math
import importlib.util

spec=importlib.util.spec_from_file_location('r51t10_audit_helpers',Path(__file__).with_name('study.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

FIELDS=('activation','inhibition','direct','associative')


def normalize(image):
    d=deepcopy(image.to_dict())
    for k in ('definition','definition_hash'):d.pop(k)
    for k in ('resource_precheck_enabled','subthreshold_expiry_enabled'):d['config'].pop(k,None)
    return d


def read_points(path):
    return s.s.unpack(path)


def stats(points):
    maxima=[max((n['activation'] for n in p['nodes'] if n['channel'] in s.TARGETS),default=0) for p in points]
    values=[n['activation'] for p in points for n in p['nodes'] if n['channel'] in s.TARGETS]
    inhibition=[n['inhibition'] for p in points for n in p['nodes'] if n['channel'] in s.TARGETS]
    return {'minimum':min(maxima),'maximum':max(maxima),'end':maxima[-1],
            'samples':len(points),'continuous':len(points)==1502 and all(v>1e-6 for v in maxima),
            'saturation_fraction':sum(v>=.95 for v in values)/len(values) if values else 0,
            'maximum_inhibition':max(inhibition,default=0)}


def independent_margin(case,points):
    start=case['probe_start_us']+round(case['gap_s']*1e6)
    correct='C' if case['cue']=='AB' else 'E'
    if case['swap']:correct='E' if correct=='C' else 'C'
    wrong='E' if correct=='C' else 'C'
    peaks={k:max((n['activation'] for p in points if p['time_us']>=start for n in p['nodes']
                  if n['channel']==s.s.measure.TOKENS[k]),default=0) for k in (correct,wrong)}
    return peaks[correct]-peaks[wrong]


def point_difference(a,b):
    if len(a)!=len(b) or [p['time_us'] for p in a]!=[p['time_us'] for p in b]:return None
    largest=0.
    for x,y in zip(a,b):
        ix={n['channel']:n for n in x['nodes']};iy={n['channel']:n for n in y['nodes']}
        for ch in set(ix)|set(iy):
            for field in FIELDS:
                largest=max(largest,abs(ix.get(ch,{}).get(field,0)-iy.get(ch,{}).get(field,0)))
    return largest


def audit(work):
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    assert s.s.read(work/'summary.json')['stages']==92
    s.check(work)
    assert not (work/'audit.json').exists()
    for name,sha in s.s.read(work/'external-manifest.json').items():assert s.s.sha(Path(name))==sha,name
    plan=s.s.read(work/'plan.json');results={};processes={};rows=[];count=0;max_error=0.
    for stage in plan:
        folder=work/'cases'/stage['key'];q=s.s.read(folder/'result.json')
        before=s.get(folder/'before-intervention.rstate.gz')
        initial=s.get(folder/'initial.rstate.gz');final=s.get(folder/'final.rstate.gz')
        for name,image in (('before',before),('initial',initial),('final',final)):
            assert image.digest==q[name+'_sha256']
            # Loading validates complete state; no advancement or stimulation.
            assert s.engine(state=image).capture_state().digest==image.digest
            count+=1
        if 'external' in stage:parent=s.get(work/stage['external'])
        elif stage.get('parent'):parent=s.get(work/'cases'/stage['parent']/'final.rstate.gz')
        else:parent=None
        if parent:
            assert parent.digest==q['parent_sha256']
            assert normalize(parent)==normalize(before)
        else:assert q['parent_sha256'] is None
        bi=before.to_dict();a=initial.to_dict();b=final.to_dict()
        assert a['config']==bi['config']|stage['patch']
        assert a['time_us']==bi['time_us']
        assert b['config']==a['config']
        assert int(b['time_us'])==q['time_us'] and b['life']==q['life']
        assert b['transport']==q['transport']
        if 'case' in stage:
            inputs=s.load_inputs(work,stage)
            assert inputs==s.s.unpack(folder/'inputs.json.gz')
            assert len(inputs)==q['scheduled'] and q['injected']<=len(inputs)
            if q['life']!='dead':assert q['injected']==len(inputs) and q['time_us']==stage['case']['end_us']
        if (folder/'course.jsonl.gz').exists():
            with gzip.open(folder/'course.jsonl.gz','rt',encoding='utf8') as f:
                last=None
                for line in f:
                    p=json.loads(line)
                    assert last is None or p['time_us']>last
                    last=p['time_us']
        row={'key':stage['key'],'group':stage['group'],'block':stage['block'],'life':q['life'],
             'wall_seconds':q['wall_seconds'],'actual_end_us':q['time_us'],
             'transmitted_excitation':b['transport']['transmitted_excitation']-a['transport']['transmitted_excitation'],
             'transmitted_inhibition':b['transport']['transmitted_inhibition']-a['transport']['transmitted_inhibition']}
        if (folder/'process.json.gz').exists():
            points=read_points(folder/'process.json.gz');processes[stage['key']]=points
            if len(points)==1502:
                times=[p['time_us']-stage['case']['probe_start_us'] for p in points]
                assert times==[0]+list(range(0,15000001,10000))
            row['activity']=stats(points)
            # The runner's field describes its recorded samples. The registered
            # persistence criterion additionally requires the complete window.
            assert q['activity']['continuous']==all(
                max((n['activation'] for n in p['nodes'] if n['channel'] in s.TARGETS),default=0)>1e-6
                for p in points)
            if stage['group'] in ('prefix','success'):
                row['margin']=independent_margin(stage['case'],points)
                if len(points)==1502:
                    max_error=max(max_error,abs(row['margin']-q['process']['signed_peak']))
                    assert max_error<1e-12
                else:
                    assert 'incomplete_process' in q
                row['passed']=len(points)==1502 and row['margin']>1e-6
        if stage['group']=='tail':
            tail=s.s.unpack(folder/'tail.json.gz');assert tail==q['tail']
            for p in tail:
                image=s.get(folder/f"tail-{p['requested_seconds']}.rstate.gz")
                d=image.to_dict();count+=1
                assert int(d['time_us'])==p['time_us'] and d['life']==p['life']
                assert d['transport']==p['transport'] and d['active']==p['active']
            last=tail[-1];zero=next((p for p in tail if not any(n['activation']>0 for n in p['nodes'])),None)
            row.update(variant=stage['variant'],fix=stage['patch']['subthreshold_expiry_enabled'],
                       actual_seconds=last['actual_seconds'],last_maximum=max((n['activation'] for n in last['nodes']),default=0),
                       remaining_active=len(last['active']),first_zero_sample_seconds=None if zero is None else zero['actual_seconds'],
                       transmission_after_first_zero=None if zero is None else sum(last['transport'][k]-zero['transport'][k]
                           for k in ('transmitted_excitation','transmitted_inhibition')))
            row['quiet_since_us']=b['quiet_since_us']
            row['quiescence_death_us']=b['config']['quiescence_death_us']
            if row['life']=='dead':
                assert row['remaining_active']==0 and row['last_maximum']==0
                assert b['quiet_since_us'] is not None
                assert int(b['time_us'])-int(b['quiet_since_us'])>=int(b['config']['quiescence_death_us'])
                row['lifecycle_outcome']='cleared_and_dead_after_quiet_period'
            elif row['last_maximum']>0:
                row['lifecycle_outcome']='actual_activation_remains'
            elif zero and last['time_us']-zero['time_us']>=int(b['config']['quiescence_death_us']):
                row['lifecycle_outcome']='zero_activation_but_alive_after_quiet_period'
            else:
                row['lifecycle_outcome']='quiet_period_not_yet_observed'
        rows.append(row);results[stage['key']]=row
    historical=[]
    for item in s.s.read(work/'historical.json'):
        folder=work/item['folder'];q=s.s.read(folder/'result.json')
        for name in ('initial','final'):
            image=s.s.ArtifactCodec.decode((folder/(name+'.tmind')).read_bytes())
            assert image.digest==q[name+'_sha256'];count+=1
        points=json.loads(lzma.open(folder/'trajectory.json.xz','rb').read())['points']
        assert len(points)==1502
        historical.append(item|stats(points))
    pairs=[]
    for key,points in processes.items():
        other=key.replace('f0','f1').replace('fix-0','fix-1')
        if other!=key and other in processes:
            pairs.append({'off':key,'on':other,'max_activity_difference':point_difference(points,processes[other])})
    persistence=[];prefix=[];success=[]
    for flags in s.FLAGS:
        for mode in ('original','short-inhibition'):
            cells=[results[f'persistent/{flags}/{b}/{mode}/probe'] for b in (0,1)]
            persistence.append({'flags':flags,'mode':mode,'passed_blocks':sum(r.get('activity',{}).get('continuous',False) for r in cells),
                                'blocks':cells})
        cells=[results[f'prefix/{flags}/{b}/{cue}'] for b in (0,1) for cue in ('AB','DB')]
        prefix.append({'flags':flags,'passed_blocks':sum(all(results[f'prefix/{flags}/{b}/{c}'].get('passed',False) for c in ('AB','DB')) for b in (0,1)),
                       'blocks':cells})
    for fix in (0,1):
        cells=[results[f'success/{b}/fix-{fix}/{cue}'] for b in (0,1) for cue in ('AB','DB')]
        success.append({'fix':fix,'passed_blocks':sum(all(results[f'success/{b}/fix-{fix}/{c}'].get('passed',False) for c in ('AB','DB')) for b in (0,1)),
                        'blocks':cells})
    analysis={'material_blocks':2,'stages':92,'persistence':persistence,'prefix':prefix,'success':success,
              'tails':[r for r in rows if r['group']=='tail'],'historical':historical,'repair_pairs':pairs,
              'execution_wall_seconds':sum(r['wall_seconds'] for r in rows),'rows':rows}
    evidence={'passed':True,'scientific_stop':False,'stages':92,'complete_states_checked':count,
              'processes_checked':len(processes),'historical_processes':len(historical),
              'independent_margin_error':max_error,'old_originals_unchanged':True,
              'original_bytes':sum(p.stat().st_size for p in work.rglob('*') if p.is_file())}
    evidence['lifecycle_clearance_passed']=not any(
        r['fix'] and r['lifecycle_outcome']=='zero_activation_but_alive_after_quiet_period'
        for r in analysis['tails'])
    evidence['scientific_stop']=not evidence['lifecycle_clearance_passed']
    s.s.write(work/'analysis.json',analysis);s.s.write(work/'audit.json',evidence)
    print(json.dumps(evidence,ensure_ascii=False))
    print(json.dumps({'persistence':[(r['flags'],r['mode'],r['passed_blocks']) for r in persistence],
                      'prefix':[(r['flags'],r['passed_blocks']) for r in prefix],
                      'success':[(r['fix'],r['passed_blocks']) for r in success],
                      'repair_maximum':max((r['max_activity_difference'] or 0 for r in pairs),default=0)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    audit(parser.parse_args().work)
