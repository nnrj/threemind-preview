"""Engineering specimens; never advances a registered research individual."""
import os
import subprocess
from dataclasses import replace

import pytest
from threemind_core import StateImage, Stimulus
from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel
from threemind_kernels.weight_decay import KERNEL_ID, RULES, CandidateEngine, configuration, exact_weight
from threemind_kernels.weight_decay_native import NativeWeightDecayEngine
from threemind_runtime import ArtifactCodec
from test_local53 import same, inputs


@pytest.mark.parametrize('rule', RULES)
@pytest.mark.parametrize('opts', ({}, {'reception_mode':'unified','arrival_mode':'coincident','propagation_phase':'asynchronous'}, {'energy_simulation_enabled':True,'energy_starvation_damage_enabled':True,'energy_initial_reserve':0.1}, {'stp_enabled':False,'fast_enabled':False,'plasticity':False}))
def test_all_state_events_cross_restore(rule, opts):
    c=configuration(908771,rule,**opts)
    a,b=CandidateEngine(c),NativeWeightDecayEngine(c)
    for s in inputs():
        a.inject(s); b.inject(s)
    for t in (0,50_000,100_000,110_000,411_337,900_000,1_000_000,5_000_000):
        x,y=[],[]
        a.advance_to(t,x.append); b.advance_to(t,y.append)
        same(x,y,'events')
        same(a.capture_state().to_dict(),b.capture_state().to_dict(),'state')
        same(a.graph(),b.graph(),'graph')
        old=a.capture_state()
        a=CandidateEngine(state=b.capture_state())
        b=NativeWeightDecayEngine(state=old)


@pytest.mark.parametrize('rule', RULES)
def test_quiet_decay_partition_and_observation(rule):
    c=configuration(908772,rule,quiescence_death_us=10**12)
    a,b,d=CandidateEngine(c),NativeWeightDecayEngine(c),NativeWeightDecayEngine(c)
    for e in (a,b,d):
        e.inject(Stimulus(0,((1,0.5),(2,0.3))))
    a.advance_to(30_000_000); b.advance_to(30_000_000)
    for t in (0,111_111,1_000_000,7_000_000,30_000_000):
        d.advance_to(t)
        before=d.capture_state().payload
        d.metrics();d.activations();d.graph();d.capture_state()
        assert before==d.capture_state().payload
    same(a.capture_state().to_dict(),b.capture_state().to_dict())
    same(b.capture_state().to_dict(),d.capture_state().to_dict())


def test_identity_defaults_and_immutable_law():
    assert DEFAULT_KERNEL=='threemind.continuous-memory/6.1'
    assert resolve_kernel('threemind.continuous-memory/5.3').configuration().decay_curve=='inverse-logarithmic'
    desc=resolve_kernel(KERNEL_ID)
    assert type(desc.create(backend='native')) is NativeWeightDecayEngine
    for backend in ('reference','native'):
        e=desc.create(backend=backend)
        assert e.capture_state().to_dict()['dynamics']==KERNEL_ID
        assert e.capture_state().to_dict()['definition']==desc.create(backend='reference').capture_state().to_dict()['definition']
        with pytest.raises(ValueError): e.reconfigure(replace(e.config,extra_rate=.01))
        with pytest.raises(ValueError): e.reconfigure(replace(e.config,retention_growth_enabled=True))
        for old in ('5.1','5.2','5.3'):
            with pytest.raises(ValueError): resolve_kernel('threemind.continuous-memory/'+old).create(state=e.capture_state(),backend=backend)
        invalid=e.capture_state().to_dict(); invalid['dynamics']='threemind.continuous-memory/5.3'
        with pytest.raises(ValueError): desc.create(state=StateImage.from_dict(invalid),backend=backend)


@pytest.mark.parametrize('rule',RULES)
@pytest.mark.parametrize('fmt',('json','tmind'))
def test_standalone_roundtrip(rule,fmt,tmp_path):
    a=CandidateEngine(configuration(908773,rule))
    for t in (0,100_000,900_000): a.inject(Stimulus(t,((1,.5),(2,.3))))
    a.advance_to(137_001)
    raw=ArtifactCodec.encode(a.capture_state(),fmt)
    src=tmp_path/('in.'+fmt);src.write_bytes(raw)
    out=tmp_path/'out.tmind';db=tmp_path/'subject.sqlite'
    runtime=os.environ['THREEMIND_TEST_RUNTIME']
    p=subprocess.run([runtime,'--model',str(src),'--clock','unbounded','--until-us','1200000','--export',str(out),'--store',str(db)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    a.advance_to(1_200_000)
    same(a.capture_state().to_dict(),ArtifactCodec.decode(out.read_bytes()).to_dict())
    assert src.read_bytes()==raw
    final=tmp_path/'final.json'
    p=subprocess.run([runtime,'--resume','--store',str(db),'--clock','unbounded','--until-us','2000000','--export',str(final)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    a.advance_to(2_000_000)
    same(a.capture_state().to_dict(),ArtifactCodec.decode(final.read_bytes()).to_dict())


def test_public_configuration_preserves_candidate_constraints():
    from threemind_lab.configuration import catalogue, default_spec, validate_configuration
    spec = default_spec(kernel_id=KERNEL_ID)
    assert validate_configuration(spec)['valid']
    fields = {r['path']: r for r in catalogue(KERNEL_ID)['fields']}
    for name in ('edge_rule', 'minimum_rate', 'extra_rate', 'matching_weight'):
        assert fields['config.'+name]['default'] == spec['config'][name]
        assert fields['config.'+name]['immutable']
    for name, value in (('extra_rate', .012), ('structure_check_interval_us', 200_000)):
        changed = {**spec, 'config': {**spec['config'], name:value}}
        assert validate_configuration(changed)['valid']
        assert not validate_configuration(changed, current=spec)['valid']
    for name in ('retention_growth_enabled', 'retention_relaxation_enabled'):
        assert not validate_configuration({**spec, 'config': {**spec['config'], name:True}})['valid']


@pytest.mark.parametrize('rule', RULES)
def test_standalone_blank_constructor(rule, tmp_path):
    import json
    c = configuration(908775, rule)
    config = tmp_path/'config.json'
    config.write_text(json.dumps(c.to_dict()), encoding='utf8')
    output = tmp_path/'blank.json'
    p = subprocess.run([os.environ['THREEMIND_TEST_RUNTIME'], '--kernel', KERNEL_ID,
                        '--config', str(config), '--until-us', '0', '--clock', 'unbounded',
                        '--export', str(output)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    same(CandidateEngine(c).capture_state().to_dict(), ArtifactCodec.decode(output.read_bytes()).to_dict())


@pytest.mark.parametrize('rule', ('weight-fast', 'weight-slow'))
@pytest.mark.parametrize('weight', (.035, .2, .5, .9, .99, 1.0))
def test_high_weight_exact_decay_native(rule, weight):
    # Declared engineering states cover strengths not reached in the formal assay.
    c = configuration(908776, rule, quiescence_death_us=10**12)
    base = CandidateEngine(c)
    base.inject(Stimulus(0, ((1,.5),(2,.5))))
    base.advance_to(0)
    base.intervene(nodes=[n['id'] for n in base.graph()['nodes']], action='silence')
    state = base.capture_state().to_dict()
    assert state['edges']
    for edge in state['edges']:
        edge['weight'] = weight
    a = CandidateEngine(state=StateImage.from_dict(state))
    b = NativeWeightDecayEngine(state=StateImage.from_dict(state))
    a.advance_to(1_000_000); b.advance_to(1_000_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())
    for edge in b.capture_state().to_dict()['edges']:
        assert edge['weight'] == pytest.approx(exact_weight(weight, 1, c.minimum_rate, c.extra_rate), rel=3e-12)
