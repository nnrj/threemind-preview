"""Independent resource pools, historical fidelity and whole-state continuity."""
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from test_local60 import inject_course, same
from test_local63 import make, numerical
from threemind_core import StateImage, Stimulus
from threemind_kernels.local63 import KERNEL_ID, Local63Config, Local63Engine
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import birth


@pytest.mark.parametrize('separate',[False,True])
@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
@pytest.mark.parametrize('patch',[{}, {'resource_precheck_enabled':False,'stp_facilitation_tau_s':.1},
    {'depletion_enabled':False}, {'stp_enabled':False}, {'inhibitory_learning_enabled':False},
    {'energy_simulation_enabled':True}, {'signal_threshold_enabled':False}])
def test_resource_backends_and_continuity(separate,distribution,mode,patch):
    c=Local63Config(inhibition_bypasses_resources=False,separate_inhibition_resources=separate,inhibition_distribution=distribution,
                    consolidation_mode=mode,quiescence_death_us=10**12,**patch)
    p,r=make(c),make(c,backend='native')
    for e in (p,r):inject_course(e)
    for t in (0,110000,900000,2100000,10000000):
        p.advance_to(t);r.advance_to(t)
        same(p.capture_state().to_dict(),r.capture_state().to_dict())
        for e in (p,r):
            before=e.capture_state();e.graph();e.metrics();e.observation_nodes()
            assert e.capture_state().digest==before.digest
            assert ArtifactCodec.decode(ArtifactCodec.encode(before)).digest==before.digest
        p=make(state=p.capture_state());r=make(state=r.capture_state(),backend='native')
    for age in ('preserve','reset'):
        parent=p.capture_state();child=birth(parent,decay_age=age)
        assert p.capture_state().digest==parent.digest
        assert child.to_dict()['config']['separate_inhibition_resources']==separate
        assert all(row['short_term'] is None and 'inhibition_short_term' not in row for row in child.to_dict()['edges'])
        same(make(state=child).capture_state().to_dict(),make(state=child,backend='native').capture_state().to_dict())


@pytest.mark.parametrize('positive',[False,True])
def test_one_signal_does_not_spend_the_other_pool(positive):
    c=Local63Config(inhibition_bypasses_resources=False,separate_inhibition_resources=True,signal_threshold_enabled=False,
                    strong_fatigue_enabled=False,fast_enabled=False)
    e=Local63Engine(c);e.inject(Stimulus(0,((1,.4),(2,.3))));e.advance_to(0)
    n=e.nodes[1];n.activation=.5 if positive else 0;n.inhibition=0 if positive else .5
    n.pending_inhibition=n.generated_inhibition=0
    before=e.edges[1,2].weight;e._emit(1);edge=e.edges[1,2]
    own=edge.short_term if positive else edge.inhibition_short_term
    other=edge.inhibition_short_term if positive else edge.short_term
    assert own is not None and own['available']<1 and other is None
    assert edge.weight>before  # Both signal types still strengthen the shared connection.
    assert edge.last_pass_us=='0'  # Emission is at zero; usage rules have not been changed.


@pytest.mark.parametrize('thresholds',[(2.,2.),(0.,2.),(2.,0.)])
def test_precheck_applies_to_each_pool(thresholds):
    p,n=thresholds
    e=Local63Engine(Local63Config(inhibition_bypasses_resources=False,separate_inhibition_resources=True,
        resource_precheck_enabled=True,activation_signal_threshold=p,inhibition_signal_threshold=n,fast_enabled=False,local_novelty_gain=0))
    e.inject(Stimulus(0,((1,.4),(2,.3))));e.advance_to(0);e.nodes[1].inhibition=.2
    e._emit(1);edge=e.edges[1,2]
    assert (edge.short_term is not None)==(p==0)
    assert (edge.inhibition_short_term is not None)==(n==0)


@pytest.mark.parametrize('backend',['reference','native'])
@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
def test_real_prechange_state_continues_identically(backend,mode,distribution):
    root=Path(__file__).resolve().parents[1]/'.work/kernel63-resources'
    if not (root/f'before-{mode}-{distribution}.json').exists():
        pytest.skip('Local prechange witness is not distributed with the test suite')
    if not (root/f'before-{mode}-{distribution}.json').exists():
        pytest.skip('Local prechange witness is not distributed with the test suite')
    initial=StateImage.from_dict(json.loads((root/f'before-{mode}-{distribution}.json').read_text('utf8')))
    expected=StateImage.from_dict(json.loads((root/f'after-{mode}-{distribution}.json').read_text('utf8')))
    e=make(state=initial,backend=backend)
    assert not e.config.separate_inhibition_resources
    e.advance_to(2100000);same(numerical(e.capture_state()),numerical(expected))
    with pytest.raises(ValueError):e.reconfigure(replace(e.config,separate_inhibition_resources=True))


@pytest.mark.parametrize('bad',[None,0,1,'false'])
def test_invalid_resource_choice(bad):
    with pytest.raises(ValueError):Local63Config(separate_inhibition_resources=bad)


def test_resource_choice_is_exposed():
    from threemind_lab.configuration import catalogue,default_spec,validate_configuration
    field=next(q for q in catalogue(KERNEL_ID)['fields'] if q['path']=='config.separate_inhibition_resources')
    assert field['default'] is False and field['immutable']
    for value in (False,True):
        assert validate_configuration(default_spec(kernel_id=KERNEL_ID)|{'config':{'separate_inhibition_resources':value}})['valid']


@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('format',['json','tmind'])
def test_standalone_independent_resources(tmp_path,distribution,format):
    runtime=Path(__file__).resolve().parents[1]/'target/release/threemind-runtime.exe'
    assert runtime.exists()
    e=make(Local63Config(inhibition_bypasses_resources=False,separate_inhibition_resources=True,inhibition_distribution=distribution))
    inject_course(e);e.advance_to(900000)
    source=tmp_path/('initial.'+format);target=tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(e.capture_state(),format))
    subprocess.run([str(runtime),'--model',str(source),'--clock','unbounded','--until-us','2100000',
                    '--export',str(target)],check=True,capture_output=True)
    e.advance_to(2100000)
    same(e.capture_state().to_dict(),ArtifactCodec.decode(target.read_bytes()).to_dict())
