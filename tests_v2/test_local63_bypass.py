"""Inhibitory bypass, old-state fidelity, and unchanged excitatory resource use."""
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


@pytest.mark.parametrize('bypass',[False,True])
@pytest.mark.parametrize('separate',[False,True])
@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('patch',[{}, {'resource_precheck_enabled':True,'subthreshold_expiry_enabled':True},
    {'stp_facilitation_tau_s':1.0,'depletion_enabled':False}, {'stp_enabled':False},
    {'inhibitory_learning_enabled':False}, {'energy_simulation_enabled':True}])
def test_bypass_backends_restore_and_reconfigure(bypass,separate,distribution,patch):
    c=Local63Config(inhibition_bypasses_resources=bypass,separate_inhibition_resources=separate,
        inhibition_distribution=distribution,quiescence_death_us=10**12,**patch)
    p,r=make(c),make(c,backend='native')
    for e in (p,r):inject_course(e)
    for when in (0,110000,900000,2100000):
        for e in (p,r):e.advance_to(when)
        same(p.capture_state().to_dict(),r.capture_state().to_dict())
        p,r=make(state=p.capture_state()),make(state=r.capture_state(),backend='native')
    for e in (p,r):
        before=e.capture_state()
        e.graph();e.metrics();e.observation_nodes()
        assert e.capture_state().digest==before.digest
        e.reconfigure(replace(e.config,inhibition_bypasses_resources=not bypass))
        assert e.time_us==2100000
        e.advance_to(4000000)
    same(p.capture_state().to_dict(),r.capture_state().to_dict())


@pytest.mark.parametrize('separate',[False,True])
@pytest.mark.parametrize('learning',[False,True])
def test_inhibition_bypasses_both_pools_but_preserves_signal_and_learning(separate,learning):
    e=Local63Engine(Local63Config(inhibition_bypasses_resources=True,separate_inhibition_resources=separate,
        inhibitory_learning_enabled=learning,signal_threshold_enabled=False,fast_enabled=False))
    e.inject(Stimulus(0,((1,.4),(2,.3))));e.advance_to(0)
    n=e.nodes[1];n.activation=0;n.inhibition=.5;n.pending_inhibition=n.generated_inhibition=0
    edge=e.edges[1,2];weight=edge.weight
    e._emit(1)
    assert edge.short_term is None and edge.inhibition_short_term is None
    assert e._emission_inhibitors[2]>0
    assert (edge.weight>weight)==learning


@pytest.mark.parametrize('separate',[False,True])
def test_excitatory_resource_use_is_unchanged(separate):
    engines=[]
    for bypass in (False,True):
        e=Local63Engine(Local63Config(inhibition_bypasses_resources=bypass,separate_inhibition_resources=separate,
            signal_threshold_enabled=False,fast_enabled=False))
        e.inject(Stimulus(0,((1,.4),(2,.3))));e.advance_to(0)
        n=e.nodes[1];n.activation=.5;n.inhibition=n.pending_inhibition=n.generated_inhibition=0
        e._emit(1);engines.append(e)
    same(numerical(engines[0].capture_state()),numerical(engines[1].capture_state()))
    assert engines[1].edges[1,2].short_term['available']<1


@pytest.mark.parametrize('backend',['reference','native'])
@pytest.mark.parametrize('mode',['adaptive-half-life','stability'])
@pytest.mark.parametrize('distribution',['per-connection','weight-proportional'])
@pytest.mark.parametrize('separate',[0,1])
def test_prechange63_snapshots_keep_resource_limited_inhibition(backend,mode,distribution,separate):
    root=Path(__file__).resolve().parents[1]/'.work/kernel63-bypass'
    stem=f'{mode}-{distribution}-{separate}'
    if not (root/(stem+'-before.json')).exists():pytest.skip('local prechange witness')
    before=StateImage.from_dict(json.loads((root/(stem+'-before.json')).read_text('utf8')))
    after=StateImage.from_dict(json.loads((root/(stem+'-after.json')).read_text('utf8')))
    e=make(state=before,backend=backend)
    assert e.config.inhibition_bypasses_resources is False
    e.advance_to(2100000)
    same(numerical(e.capture_state()),numerical(after))


@pytest.mark.parametrize('bad',[None,0,1,'true'])
def test_invalid_bypass(bad):
    with pytest.raises(ValueError):Local63Config(inhibition_bypasses_resources=bad)


def test_default_and_catalogue():
    from threemind_lab.configuration import catalogue,default_spec,validate_configuration
    assert Local63Config().inhibition_bypasses_resources is False
    assert Local63Config().separate_inhibition_resources is False
    field=next(q for q in catalogue(KERNEL_ID)['fields'] if q['path']=='config.inhibition_bypasses_resources')
    assert field['default'] is False
    for bypass in (False,True):
        assert validate_configuration(default_spec(kernel_id=KERNEL_ID)|
            {'config':{'inhibition_bypasses_resources':bypass}})['valid']


@pytest.mark.parametrize('format',['json','tmind'])
@pytest.mark.parametrize('old',[False,True])
def test_standalone_bypass_and_old_snapshot(tmp_path,format,old):
    root=Path(__file__).resolve().parents[1]
    if old:
        source=root/'.work/kernel63-bypass/adaptive-half-life-per-connection-1-before.json'
        if not source.exists():pytest.skip('local prechange witness')
        image=StateImage.from_dict(json.loads(source.read_text('utf8')))
        e=make(state=image)
    else:
        e=make(Local63Config(inhibition_bypasses_resources=True,separate_inhibition_resources=True))
        inject_course(e);e.advance_to(900000);image=e.capture_state()
    source,target=tmp_path/('initial.'+format),tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(image,format))
    subprocess.run([str(root/'target/release/threemind-runtime.exe'),'--model',str(source),
        '--clock','unbounded','--until-us','2100000','--export',str(target)],check=True,capture_output=True)
    e.advance_to(2100000)
    same(e.capture_state().to_dict(),ArtifactCodec.decode(target.read_bytes()).to_dict())
