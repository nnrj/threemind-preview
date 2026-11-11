"""Engineering prerequisites for R46b; requires R46a's safe scientific exit."""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path
from threemind_core.engine import canonical_bytes
import assay_study as a
from assay_resume import accelerated,dead
from stimulus_assay import StimulusAssay,cases


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)


def target(sample):
    return [e for e in sample['graph']['edges'] if {e['source_symbol'],e['target_symbol']}=={'cue','out0'}]


def raw_targets(sample,mapping):
    ids={n['id'] for n in sample['core']['nodes'] if n['channel'] in (mapping['cue'],mapping['out0'])}
    return [e for e in sample['core']['edges'] if e['source'] in ids and e['target'] in ids]


def weights(sample):return sorted(e['weight'] for e in target(sample))


def config_diff(x,y):
    return {k for k in x if x[k]!=y[k]}


def run(output):
    assert dead(a.load(a.WORK/'host.json')),'scientific hosts remain serial'
    assert a.load(a.WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((a.WORK/n).exists() for n in ('STOP','in-flight.json'))
    assert not output.exists(),'preserve an earlier engineering attempt'
    output.mkdir(parents=True);started=time.monotonic();results=[];cost=[]
    a.frozen(a.WORK)
    source_names=('stimulus_assay.py','check_stimulus_assay.py','check_stimulus_assay_v2.py','check_stimulus_assay_v3.py','test_stimulus_design.py',
        'stimulus_protocol_draft.zh.md','stimulus_protocol_draft.en.md',
        'exact_acceleration_v2.py','assay_resume.py')
    sources={n:a.sha(a.HERE/n) for n in source_names}
    implementation=a.base.capture_implementation('reference')
    save(output/'source-manifest.json',sources);save(output/'implementation.json',implementation)
    for name in source_names:
        target_path=output/'frozen'/name;target_path.parent.mkdir(parents=True,exist_ok=True)
        with target_path.open('xb') as stream:stream.write((a.HERE/name).read_bytes())
    a.base.resource_check(output)
    save(output/'prospective-checks.json',dict(scientific_n=0,wall_budget_seconds=600,
        purpose='Actual stimulus fields, gain engagement, full-state restoration and exact acceleration before registration.',
        expected=['Equal actual drive and immediate activation across intensity conditions.',
            'Only intensity_gain or local_novelty_gain differs in its matched causal contrast.',
            'Strong gain increases target birth weights; novelty obtains eligible windows and positive awards.',
            'The complete next temporal probe matches after save/restore and exact acceleration.'],
        engineering_seed_offset=9000,long_probe_examples='origin 0, both families, all six settings'))
    with a.Guard(output):
        for original in cases():
            if original['delay']!=1 or not original['cue']:continue
            assert time.monotonic()-started<600,'engineering wall budget'
            a.base.resource_check(output)
            if (output/'STOP').exists():raise RuntimeError('engineering guard stopped')
            c=copy.deepcopy(original);c['seed']+=9000;c['key']='engineering/'+c['key']
            previous=a.ROOT/'.work/r46b-instrument-v1'
            old_manifest=a.load(previous/'source-manifest.json')
            for name,h in old_manifest.items():assert a.sha(a.HERE/name)==h,name
            source_path=previous/'fixtures'/original['key']/'complete.json.gz'
            result=a.load(source_path)
            assert result['case']==c and result['restoration_and_acceleration_exact'] and result['teaching_acceleration_exact']
            target_path=output/'fixtures'/original['key']/'complete.json.gz'
            target_path.parent.mkdir(parents=True,exist_ok=True)
            with target_path.open('xb') as stream:stream.write(source_path.read_bytes())
            assert a.sha(target_path)==a.sha(source_path)
            results.append(result)
        lookup={(r['case']['origin'],r['case']['curve'],r['case']['relaxation'],r['case']['arm']):r for r in results}
        checks=[]
        for o in range(8):
            for curve in ('exponential','inverse-logarithmic','power-law'):
                for relaxation in (True,False):
                    get=lambda arm:lookup[o,curve,relaxation,arm]
                    normal,strong,off=[get(x) for x in ('equal-drive-normal','strong-intensity','strong-gain-zero')]
                    assert config_diff(strong['birth']['core']['config'],off['birth']['core']['config'])=={'intensity_gain'}
                    ns,ss,os=[r['taught']['samples']['immediate'] for r in (normal,strong,off)]
                    node=lambda sample,c:next(n for n in sample['core']['nodes'] if n['channel']==c)
                    for name in ('cue','out0'):
                        channel=strong['birth']['mapping'][name]
                        n,s,z=[node(sample,channel) for sample in (ns,ss,os)]
                        assert n['activation']==s['activation']==z['activation']
                        assert n['fatigue']==0 and s['fatigue']==z['fatigue']>0
                    assert len(weights(ss))==len(weights(os))==2
                    assert all(x>y for x,y in zip(weights(ss),weights(os)))
                    novel,no_novel=get('arrival-novelty'),get('arrival-gain-zero')
                    assert config_diff(novel['birth']['core']['config'],no_novel['birth']['core']['config'])=={'local_novelty_gain'}
                    prior_normal=copy.deepcopy(novel['taught']['samples']['before_new'])
                    prior_zero=copy.deepcopy(no_novel['taught']['samples']['before_new'])
                    for prior in (prior_normal,prior_zero):
                        encoded=canonical_bytes(prior['core']['definition'])
                        assert hashlib.sha256(encoded).hexdigest()==prior['core']['definition_hash']
                    prior_normal['core']['config']['local_novelty_gain']=0.
                    prior_normal['core']['definition']['config']['local_novelty_gain']=0.
                    assert prior_normal['core']['definition']==prior_zero['core']['definition']
                    prior_normal['core']['definition_hash']=hashlib.sha256(canonical_bytes(prior_normal['core']['definition'])).hexdigest()
                    assert prior_normal==prior_zero,'prior dynamics differ beyond declared configuration and its identity metadata'
                    pending=raw_targets(novel['taught']['samples']['pending'],novel['birth']['mapping'])
                    closed=raw_targets(novel['taught']['samples']['after_window'],novel['birth']['mapping'])
                    assert len(pending)==2 and all(e['novelty_deadline_us'] is not None for e in pending)
                    assert all(e['novelty_deadline_us'] is None and max(e['novelty_source'],e['novelty_target'])>0 for e in closed)
                    cfg=novel['birth']['core']['config']
                    awards=[cfg['local_novelty_gain']*max(0.,1-max(e['novelty_source'],e['novelty_target'])/cfg['novelty_touch_reference']) for e in closed]
                    assert all(value>0 for value in awards),'eligible window did not yield a positive novelty award'
                    nw=weights(novel['taught']['samples']['after_window'])
                    zw=weights(no_novel['taught']['samples']['after_window'])
                    assert len(nw)==len(zw)==2 and all(x>y for x,y in zip(nw,zw))
                    checks.append(dict(origin=o,curve=curve,relaxation=relaxation,
                        strong_weights=weights(ss),strong_gain_zero_weights=weights(os),
                        novelty_weights=nw,novelty_gain_zero_weights=zw,novelty_awards=awards,
                        prior_experience_equal_except_gain=True,passed=True))
        for r in results:
            c=r['case']
            if c['origin']!=0 or c['arm'] not in ('strong-intensity','arrival-novelty'):continue
            assert time.monotonic()-started<600,'engineering wall budget'
            a.base.resource_check(output)
            if (output/'STOP').exists():raise RuntimeError('engineering guard stopped')
            s=StimulusAssay.restore(r['taught_state']);begin=time.perf_counter()
            with accelerated():result=s.first_probe(300,True)
            a.save(output/'long-probes'/c['key'].replace('d1/','d300/')/'complete.json.gz',dict(result=result,state=s.state()))
            cost.append(dict(curve=c['curve'],relaxation=c['relaxation'],family=c['family'],
                             wall_seconds=time.perf_counter()-begin))
    assert sources=={n:a.sha(a.HERE/n) for n in source_names}
    assert implementation==a.base.capture_implementation('reference')
    out=dict(scientific_n=0,passed=True,short_sequences=len(results),paired_conditions=len(checks),
        engineering_revision=3,reused_short_fixture_count=240,first_attempt='r46b-instrument-v1',
        long_probes=cost,checks=checks,wall_seconds=time.monotonic()-started,source_sha256=sources,
        implementation=implementation)
    save(output/'verified.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('implementation','checks')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
