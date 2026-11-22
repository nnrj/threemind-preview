"""6.3 version fidelity, local transmission and complete-state continuity."""
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_local60 import inject_course, same
from threemind_core import StateImage, Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local62 import Local62Config, Local62Engine
from threemind_kernels.local63 import KERNEL_ID, Local63Config, Local63Engine, Local63Node, Local63Edge
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import birth


def make(c=None, state=None, backend="reference"):
    return resolve_kernel(KERNEL_ID).create(c, state, backend=backend)


def numerical(image):
    d=copy.deepcopy(image.to_dict())
    for k in ('schema','dynamics','config','definition','definition_hash'):
        d.pop(k)
    return d


@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
@pytest.mark.parametrize('updates',[False,True])
@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('patch',[{}, {'novelty_mode':'immediate'}, {'depletion_enabled':False,'stp_facilitation_tau_s':.1},
    {'resource_precheck_enabled':True,'subthreshold_expiry_enabled':True}, {'energy_simulation_enabled':True}, {'inhibitory_learning_enabled':False},
    {'spatial_embedding':True}, {'deletion_strategy':'global-scan'}, {'reinforcement_age_policy':'reset'}])
def test_backends_continuity(mode,updates,distribution,patch):
    c=Local63Config(consolidation_mode=mode,inhibition_updates_usage=updates,inhibition_distribution=distribution,
                    quiescence_death_us=10**12,**patch)
    p,r=make(c),make(c,backend='native')
    for e in (p,r): inject_course(e)
    for t in (0,110000,900000,2100000,10000000):
        p.advance_to(t);r.advance_to(t)
        same(p.capture_state().to_dict(),r.capture_state().to_dict())
        for e in (p,r):
            before=e.capture_state(); e.graph();e.metrics();e.observation_nodes()
            assert e.capture_state().digest==before.digest
            assert ArtifactCodec.decode(ArtifactCodec.encode(before)).digest==before.digest
        p=make(state=p.capture_state());r=make(state=r.capture_state(),backend='native')


@pytest.mark.parametrize('updates',[False,True])
@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
def test_removed_options_preserve_shared_dynamics(updates,mode):
    c=Local63Config(inhibition_bypasses_resources=False,inhibition_updates_usage=updates,consolidation_mode=mode,quiescence_death_us=10**12)
    old=Local62Engine(Local62Config(**{k:v for k,v in c.to_dict().items() if k not in ('inhibition_distribution','inhibition_bypasses_resources')}))
    new=make(c)
    for e in (old,new):inject_course(e)
    for t in (0,110000,900000,2100000):
        old.advance_to(t);new.advance_to(t)
        same(numerical(old.capture_state()),numerical(new.capture_state()))


@pytest.mark.parametrize('key',['separate_inhibition','separate_inhibition_weights','separate_inhibition_learning'])
def test_separation_is_absent_not_hidden(key):
    assert key not in Local63Config().to_dict()
    with pytest.raises(ValueError):resolve_kernel(KERNEL_ID).configuration({key:False})


@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('updates',[False,True])
def test_inhibition_offer_ratio_and_usage(distribution,updates):
    c=Local63Config(plasticity=False,fast_enabled=False,stp_enabled=False,spatial_embedding=False,
                    signal_threshold_enabled=False,inhibition_updates_usage=updates,inhibition_distribution=distribution)
    e=make(c);e.time_us=1000
    for i in (10,20,30):e.nodes[i]=Local63Node(i,i,birth_serial=i,state_us='1000',energy_us='1000')
    e.nodes[10].inhibition=.4
    for target,weight in ((20,.8),(30,.4)):
        e.edges[10,target]=Local63Edge(10,target,weight,state_us='1000',last_pass_us='123')
    e.outgoing[10]={(10,20),(10,30)}
    expected=e._soft(e._soft(.4))*min(1,c.inhibition_diffusion_rate*c.propagation_interval_us/1e6)
    e._emit(10)
    a,b=(e._emission_inhibitors[i] for i in (20,30))
    assert a/b==pytest.approx(2)
    assert a+b==pytest.approx(expected*(1 if distribution=='weight-proportional' else 1.2))
    assert all(x.last_pass_us==('1000' if updates else '123') for x in e.edges.values())


@pytest.mark.parametrize('backend',['reference','native'])
@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
def test_preexisting62_artifacts_keep_updates(backend,mode):
    root=Path(__file__).resolve().parents[1]/'.work/kernel63'
    if not (root/f'before-{mode}.json').exists():pytest.skip('local pre-change witness')
    old=StateImage.from_dict(json.loads((root/f'before-{mode}.json').read_text('utf8')))
    e=resolve_kernel('threemind.continuous-memory/6.2').create(state=old,backend=backend)
    assert e.config.inhibition_updates_usage is True
    e.advance_to(2100000)
    expected=StateImage.from_dict(json.loads((root/f'before-{mode}-next.json').read_text('utf8')))
    same(numerical(e.capture_state()),numerical(expected))


@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('age',['preserve','reset'])
def test_inherited_state_and_identity(distribution,age):
    p=make(Local63Config(inhibition_distribution=distribution));inject_course(p);p.advance_to(900000)
    original=p.capture_state();child=birth(original,decay_age=age)
    assert p.capture_state().digest==original.digest
    assert child.to_dict()['dynamics']==KERNEL_ID and child.to_dict()['time_us']=='0'
    assert child.to_dict()['config']['inhibition_distribution']==distribution
    same(make(state=child).capture_state().to_dict(),make(state=child,backend='native').capture_state().to_dict())
    with pytest.raises(ValueError):resolve_kernel('threemind.continuous-memory/6.2').create(state=child)


@pytest.mark.parametrize('bad',[None,'normalized',True,0])
def test_bad_distribution(bad):
    with pytest.raises(ValueError):Local63Config(inhibition_distribution=bad)


def test_configuration_catalogue_has_no_removed_controls():
    from threemind_lab.configuration import catalogue,default_spec,validate_configuration
    cat=catalogue(kernel_id=KERNEL_ID)
    fields={q['path']:q for q in cat['fields']}
    assert {k for k in fields if k.startswith('config.separate_inhibition')} == {'config.separate_inhibition_resources'}
    assert fields['config.separate_inhibition_resources']['default'] is False
    assert fields['config.inhibition_updates_usage']['default'] is True
    assert fields['config.inhibition_distribution']['default']=='per-connection'
    assert validate_configuration(default_spec(kernel_id=KERNEL_ID))['valid']


@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('updates',[False,True])
@pytest.mark.parametrize('format',['json','tmind'])
def test_standalone_runtime_preserves_new_choices(tmp_path,distribution,updates,format):
    import subprocess
    runtime=Path(__file__).resolve().parents[1]/'target/release/threemind-runtime.exe'
    if not runtime.exists():pytest.skip('standalone runtime not built')
    e=make(Local63Config(inhibition_distribution=distribution,inhibition_updates_usage=updates,
                        consolidation_mode='stability',novelty_mode='immediate'))
    inject_course(e);e.advance_to(100000)
    source=tmp_path/('initial.'+format);target=tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(e.capture_state(),format))
    subprocess.run([str(runtime),'--model',str(source),'--clock','unbounded','--until-us','2100000',
                    '--export',str(target)],check=True,capture_output=True)
    e.advance_to(2100000)
    same(e.capture_state().to_dict(),ArtifactCodec.decode(target.read_bytes()).to_dict())
